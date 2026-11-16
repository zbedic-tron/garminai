"""No network: verified subject + D1 receipt + Neon commit + D1 ACK."""
import hashlib
import unittest

from garminai_public.identity import DemoIdentityVerifier
from garminai_public.garmin_edge_to_neon_v117 import (
    CONFIRM, PREFIX, _bridge_config, _digest, recipient_for, deliver_for_principal,
    EdgeBridgeError,
)
from garminai_public.garmin_push_inbox_v111 import OfflinePostgresPushInbox
from test_garmin_push_inbox_v111 import FakePg, DB

TOKEN='OFFLINE_TEST_ONLY_BRIDGE_TOKEN_NOT_A_REAL_SECRET_1234567890'
URL='https://garminai-synthetic-edge-v116.zbedic.workers.dev'

class FakeEdge:
    def __init__(self,db=None):
        self.calls=[];self.receipts={};self.ack_fail=False;self.fail_step=None;self.digests_tampered=False
        self.db=db
    def exchange(self, action, tenant, event):
        self.calls.append(action)
        if self.fail_step==action:
            raise EdgeBridgeError('OFFLINE_SIMULATED_FAILURE')
        key=(tenant,event)
        if action=='seed' and key not in self.receipts:
            self.receipts[key]={'ack':False}
        if key not in self.receipts:
            raise EdgeBridgeError('MISSING_RECEIPT')
        if action=='ack':
            if self.ack_fail:raise EdgeBridgeError('OFFLINE_ACK_FAILURE')
            # Prove ACK only occurs AFTER the matching Neon write is committed.
            assert self.db and any(aid==event for _,aid in self.db.inbox)
            self.receipts[key]['ack']=True
        ack=self.receipts[key]['ack']
        digest=_digest(tenant,event) if not self.digests_tampered else '0'*64
        return {'mode':'SYNTHETIC_BRIDGE_ONLY','status':'ACKED_SYNTHETIC' if ack else 'PENDING_SYNTHETIC',
                'event_id':event,'payload_digest':digest,'acknowledged':ack}

class BridgeE2ETests(unittest.TestCase):
    def setUp(self):
        signer=DemoIdentityVerifier(b'test-signer-test-signer-test-signer-1')
        self.a=signer.verify(signer.issue_for_test('alice'))
        self.b=signer.verify(signer.issue_for_test('bob'))
        self.db=FakePg();self.store=OfflinePostgresPushInbox(DB,connection_factory=self.db.connect)
        self.edge=FakeEdge(self.db)
        self.env={'GARMINAI_EDGE_BRIDGE_STAGING_ENABLED':'1','GARMINAI_EDGE_BRIDGE_URL':URL,
                  'GARMINAI_EDGE_BRIDGE_TOKEN':TOKEN}
    def go(self,who,confirmation=CONFIRM,**options):
        return deliver_for_principal(who,confirmation,env=self.env,
            lookup=lambda p: self.db.link.get(p.subject),store=self.store,edge=self.edge,**options)
    def test_first_and_repeat_pass_one_record_per_subject(self):
        self.assertEqual(self.go(self.a)['status'],'PASS')
        self.assertEqual(self.edge.calls,['seed','claim','ack'])
        self.assertEqual(self.go(self.a)['status'],'PASS')
        self.assertEqual(len(self.db.inbox),1)
        self.assertTrue(next(iter(self.db.inbox))[1].startswith(PREFIX))
        self.assertNotIn('GARMIN_A',repr(self.db.inbox))
    def test_two_subjects_disjoint_in_both_stores(self):
        self.assertEqual(self.go(self.a)['status'],'PASS')
        self.assertEqual(self.go(self.b)['status'],'PASS')
        self.assertEqual(len(self.db.inbox),2)
        self.assertEqual({k[0] for k in self.db.inbox},{'alice','bob'})
        self.assertEqual(len(self.edge.receipts),2)
        self.assertNotEqual(recipient_for(self.a,TOKEN),recipient_for(self.b,TOKEN))
    def test_pending_ack_recovers_on_retry(self):
        self.edge.ack_fail=True
        x=self.go(self.a);self.assertEqual(x['status'],'NEON_COMMITTED_EDGE_ACK_PENDING')
        self.assertEqual(len(self.db.inbox),1)
        self.edge.ack_fail=False
        self.assertEqual(self.go(self.a)['status'],'PASS')
        self.assertEqual(len(self.db.inbox),1)
        self.assertTrue(next(iter(self.edge.receipts.values()))['ack'])
    def test_db_failure_leaves_d1_unacked(self):
        self.db.migrated=False
        self.assertEqual(self.go(self.a)['status'],'NEON_WRITE_NOT_CONFIRMED')
        self.assertFalse(next(iter(self.edge.receipts.values()))['ack'])
        self.assertEqual(self.db.inbox,{})
        self.db.migrated=True
        self.assertEqual(self.go(self.a)['status'],'PASS')
    def test_d1_read_failed_no_neon_write(self):
        self.edge.fail_step='claim'
        self.assertEqual(self.go(self.a)['status'],'EDGE_NOT_READY')
        self.assertEqual(self.db.inbox,{})
    def test_receipt_digest_mismatch_no_neon_write(self):
        self.edge.digests_tampered=True
        self.assertEqual(self.go(self.a)['status'],'EDGE_RECEIPT_MISMATCH')
        self.assertEqual(self.db.inbox,{})
    def test_wrong_confirmation_no_write(self):
        r=self.go(self.a,'NO');self.assertEqual(r['status'],'CONFIRMATION_REQUIRED')
        self.assertEqual(self.edge.calls,[])
    def test_operator_disabled_no_write(self):
        self.env['GARMINAI_EDGE_BRIDGE_STAGING_ENABLED']='0'
        self.assertEqual(self.go(self.a)['status'],'OPERATOR_DISABLED')
        self.assertEqual(self.edge.calls,[])
    def test_missing_link_no_d1_seed(self):
        self.db.link.pop('alice')
        self.assertEqual(self.go(self.a)['status'],'GARMIN_LINK_REQUIRED')
        self.assertEqual(self.edge.calls,[])
    def test_missing_credentials_neon_refuses_ack(self):
        self.db.credentials.remove('alice')
        self.assertEqual(self.go(self.a)['status'],'NEON_WRITE_NOT_CONFIRMED')
        self.assertFalse(next(iter(self.edge.receipts.values()))['ack'])
    def test_wrong_link_inside_store_no_ack(self):
        r=deliver_for_principal(self.a,CONFIRM,env=self.env,lookup=lambda _:'GARMIN_B',
                                store=self.store,edge=self.edge)
        self.assertEqual(r['status'],'NEON_WRITE_NOT_CONFIRMED')
        self.assertEqual(self.db.inbox,{})
    def test_invalid_principal_rejected(self):
        self.assertEqual(self.go('alice')['status'],'NEON_AUTH_REQUIRED')
    def test_config_never_accepts_arbitrary_urls(self):
        self.assertIsNotNone(_bridge_config(self.env))
        for url in ['http://'+URL[8:], 'https://127.0.0.1',URL+'/path',URL+'?x=1',
                    URL+'@evil.example',URL+':8443',URL+'#fragment',
                    'https://garminai-synthetic-edge-v116.zbedic.workers.dev.evil.com']:
            self.assertIsNone(_bridge_config({**self.env,'GARMINAI_EDGE_BRIDGE_URL':url}))
    def test_config_requires_strong_secret(self):
        self.assertIsNone(_bridge_config({**self.env,'GARMINAI_EDGE_BRIDGE_TOKEN':'short'}))
    def test_errors_never_reveal_credentials(self):
        self.edge.fail_step='seed'
        r=self.go(self.a)
        self.assertNotIn(TOKEN,repr(r));self.assertNotIn('GARMIN_A',repr(r))
        self.assertNotIn('zbedic.workers.dev',repr(r))
    def test_schema_receipt_digest_is_deterministic(self):
        tenant,event=recipient_for(self.a,TOKEN)
        self.assertEqual(_digest(tenant,event),hashlib.sha256((tenant+'\0'+event+'\0SYNTHETIC_BRIDGE').encode()).hexdigest())

if __name__=='__main__':unittest.main()
