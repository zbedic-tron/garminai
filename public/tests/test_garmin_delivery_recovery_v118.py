"""Offline/controlled fault injection only; no real Render/D1/Neon calls."""
import json
import unittest
from unittest.mock import patch

import httpx
from garminai_public.identity import DemoIdentityVerifier
from garminai_public.garmin_push_inbox_v111 import OfflinePostgresPushInbox
from garminai_public.garmin_delivery_recovery_v118 import (
    CONFIRM, PREFIX, MODE, SCENARIOS, RecoveryError, RecoveryEdgeClient,
    recipient_for_recovery, recovery_digest, rehearse_for_principal,
    status_for_principal,
)
from test_garmin_push_inbox_v111 import FakePg, DB

TOKEN = 'V118_ONLY_TEST_BRIDGE_TOKEN_LONG_RANDOM_SHAPE_FAKE_0012345'
URL = 'https://garminai-synthetic-edge-v116.zbedic.workers.dev'


class FakeRecoveryEdge:
    def __init__(self, db):
        self.db = db
        self.receipts = {}
        self.calls = []
        self.fail_action = None
        self.bad_digest = False
        self.ack_fail = False

    def exchange(self, action, tenant, event):
        self.calls.append(action)
        if self.fail_action == action or (action == 'ack' and self.ack_fail):
            raise RecoveryError('TEST_ONLY_ERROR')
        key = (tenant, event)
        if action == 'seed':
            self.receipts.setdefault(key, {'ack': False, 'attempts': 0})
        item = self.receipts.get(key)
        if item is None:
            if action == 'inspect':
                return None
            raise RecoveryError('MISSING_TEST_RECEIPT')
        if action == 'claim':
            item['attempts'] += 1
        if action == 'ack':
            assert any(aid == event for _, aid in self.db.inbox), 'ACK before Neon commit'
            item['ack'] = True
        return {
            'mode': MODE, 'status': 'ACKED_SYNTHETIC' if item['ack'] else 'PENDING_SYNTHETIC',
            'event_id': event,
            'payload_digest': '0'*64 if self.bad_digest else recovery_digest(tenant,event),
            'acknowledged': item['ack'], 'attempts': item['attempts'],
        }


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        verifier = DemoIdentityVerifier(b'test-signer-test-signer-test-signer-1')
        self.a = verifier.verify(verifier.issue_for_test('alice'))
        self.b = verifier.verify(verifier.issue_for_test('bob'))
        self.db = FakePg()
        self.store = OfflinePostgresPushInbox(DB, connection_factory=self.db.connect)
        self.edge = FakeRecoveryEdge(self.db)
        self.env = {
            'GARMINAI_EDGE_RECOVERY_STAGING_ENABLED': '1',
            'GARMINAI_EDGE_BRIDGE_URL': URL,
            'GARMINAI_EDGE_BRIDGE_TOKEN': TOKEN,
        }

    def go(self, scenario='RECOVER', who=None, confirmation=CONFIRM):
        return rehearse_for_principal(who or self.a, confirmation, scenario,
            env=self.env, lookup=lambda p: self.db.link.get(p.subject),
            store=self.store, edge=self.edge)

    def inspect(self, who=None):
        return status_for_principal(who or self.a, env=self.env, edge=self.edge)

    def test_no_side_effect_without_operator_and_confirmation(self):
        self.env['GARMINAI_EDGE_RECOVERY_STAGING_ENABLED']='0'
        self.assertEqual(self.go()['status'], 'OPERATOR_DISABLED')
        self.env['GARMINAI_EDGE_RECOVERY_STAGING_ENABLED']='1'
        self.assertEqual(self.go(confirmation='wrong')['status'], 'CONFIRMATION_REQUIRED')
        self.assertEqual(self.go(scenario='REAL_GARMIN')['status'], 'INVALID_SCENARIO')
        self.assertFalse(self.edge.calls)
        self.assertFalse(self.db.inbox)

    def test_full_manual_recovery_chain(self):
        self.assertEqual(self.inspect()['status'], 'NOT_STARTED')
        x = self.go('SIMULATE_RENDER_DELAY')
        self.assertEqual(x['status'], 'SIMULATED_RENDER_DELAY_D1_PENDING')
        self.assertFalse(x['neon_write_attempted'])
        self.assertEqual(self.edge.calls, ['inspect', 'seed'])
        self.assertEqual(self.inspect()['d1_claim_attempts'], 0)
        self.assertEqual(self.go('SIMULATE_NEON_UNAVAILABLE')['status'],
                         'SIMULATED_NEON_UNAVAILABLE_D1_PENDING')
        self.assertEqual(self.inspect()['d1_claim_attempts'], 1)
        self.assertFalse(self.db.inbox)
        self.assertEqual(self.go('SIMULATE_D1_ACK_UNAVAILABLE')['status'],
                         'SIMULATED_D1_ACK_UNAVAILABLE_NEON_COMMITTED')
        self.assertEqual(len(self.db.inbox), 1)
        self.assertFalse(self.inspect()['d1_acknowledged'])
        passed = self.go('RECOVER')
        self.assertEqual(passed['status'],'PASS')
        self.assertEqual(passed['d1_claim_attempts'], 3)
        self.assertTrue(self.inspect()['d1_acknowledged'])
        self.assertEqual(len(self.db.inbox), 1)
        self.assertEqual(self.go()['status'], 'PASS')
        self.assertEqual(len(self.db.inbox), 1)
        self.assertNotIn('alice', json.dumps(self.inspect()))
        self.assertNotIn('GARMIN_A', json.dumps(self.inspect()))

    def test_neon_genuine_storage_failure_preserves_pending_and_can_retry(self):
        self.db.migrated=False
        self.assertEqual(self.go()['status'], 'NEON_WRITE_NOT_CONFIRMED')
        self.assertFalse(self.inspect()['d1_acknowledged'])
        self.assertEqual(len(self.db.inbox), 0)
        self.db.migrated=True
        self.assertEqual(self.go()['status'], 'PASS')
        self.assertEqual(len(self.db.inbox), 1)

    def test_genuine_edge_ack_failure_recovers_without_second_insert(self):
        self.edge.ack_fail=True
        self.assertEqual(self.go()['status'], 'NEON_COMMITTED_D1_ACK_PENDING')
        self.assertFalse(self.inspect()['d1_acknowledged'])
        self.assertEqual(len(self.db.inbox), 1)
        self.edge.ack_fail=False
        self.assertEqual(self.go()['status'], 'PASS')
        self.assertEqual(len(self.db.inbox), 1)

    def test_d1_unavailable_does_not_write_neon(self):
        self.edge.fail_action = 'claim'
        self.assertEqual(self.go()['status'], 'EDGE_RECOVERY_NOT_READY')
        self.assertFalse(self.db.inbox)

    def test_wrong_digest_fails_before_neon(self):
        self.edge.bad_digest=True
        self.assertEqual(self.go()['status'], 'EDGE_RECOVERY_NOT_READY')
        self.assertFalse(self.db.inbox)

    def test_status_read_only_works_with_operator_off(self):
        self.go('SIMULATE_RENDER_DELAY')
        self.env['GARMINAI_EDGE_RECOVERY_STAGING_ENABLED']='0'
        original=list(self.edge.calls)
        self.assertEqual(self.inspect()['status'], 'PENDING_SYNTHETIC')
        self.assertEqual(self.edge.calls,original+['inspect'])
        self.assertEqual(self.go()['status'], 'OPERATOR_DISABLED')

    def test_two_user_isolation_and_single_fixed_event(self):
        self.assertNotEqual(recipient_for_recovery(self.a,TOKEN),
                            recipient_for_recovery(self.b,TOKEN))
        self.assertEqual(self.go(who=self.a)['status'], 'PASS')
        self.assertEqual(self.inspect(who=self.b)['status'], 'NOT_STARTED')
        self.assertEqual(self.go(who=self.b)['status'], 'PASS')
        self.assertEqual(len(self.db.inbox), 2)
        self.assertEqual({subject for subject,_ in self.db.inbox}, {'alice','bob'})
        self.assertTrue(all(aid.startswith(PREFIX) for _,aid in self.db.inbox))
        self.assertEqual(len(self.edge.receipts), 2)

    def test_link_required_and_no_send(self):
        self.db.link.pop('alice')
        self.assertEqual(self.go()['status'], 'GARMIN_LINK_REQUIRED')
        self.assertFalse(self.edge.calls)

    def test_acked_fault_scenarios_cannot_reset_receipt(self):
        self.assertEqual(self.go()['status'], 'PASS')
        self.assertEqual(self.go('SIMULATE_NEON_UNAVAILABLE')['status'],
                         'SCENARIO_ALREADY_RECOVERED')
        self.assertTrue(self.inspect()['d1_acknowledged'])

    def test_secret_not_in_config_or_status(self):
        self.assertNotIn(TOKEN, repr(self.inspect()))
        bad = dict(self.env,GARMINAI_EDGE_BRIDGE_URL='http://127.0.0.1')
        self.assertEqual(status_for_principal(self.a,env=bad)['status'],
                         'EDGE_RECOVERY_CONFIG_NOT_READY')
        self.assertEqual(rehearse_for_principal(None,CONFIRM,'RECOVER',env=self.env)['status'],
                         'NEON_AUTH_REQUIRED')

    def test_all_scenarios_are_explicit_synthetic(self):
        self.assertEqual(len(SCENARIOS),4)
        self.assertEqual(len(PREFIX)+32,56)


class RecoveryHttpClientTests(unittest.TestCase):
    def test_response_validation_and_safe_errors(self):
        verifier=DemoIdentityVerifier(b'test-signer-test-signer-test-signer-1')
        principal=verifier.verify(verifier.issue_for_test('alice'))
        tenant,event=recipient_for_recovery(principal,TOKEN)
        good={'mode':MODE,'status':'PENDING_SYNTHETIC','event_id':event,
              'payload_digest':recovery_digest(tenant,event),'acknowledged':False,'attempts':0}
        def client(payload=good,code=200,ctype='application/json'):
            def handler(req):
                self.assertEqual(req.url.host,'garminai-synthetic-edge-v116.zbedic.workers.dev')
                self.assertEqual(req.headers.get('x-bridge-token'),TOKEN)
                return httpx.Response(code,json=payload,headers={'content-type':ctype})
            return lambda: httpx.Client(transport=httpx.MockTransport(handler))
        edge=RecoveryEdgeClient(URL,TOKEN,client_factory=client())
        self.assertEqual(edge.exchange('inspect',tenant,event)['attempts'],0)
        self.assertIsNone(RecoveryEdgeClient(URL,TOKEN,client_factory=client(
            {'mode':MODE,'status':'SYNTHETIC_EVENT_NOT_FOUND'},code=404)
        ).exchange('inspect',tenant,event))
        with self.assertRaises(RecoveryError):
            RecoveryEdgeClient(URL,TOKEN,client_factory=client(
                {'mode':MODE,'status':'NOT_FOUND'},code=404)
            ).exchange('inspect',tenant,event)
        for payload,code in [({**good,'attempts':True},200),({**good,'event_id':'alien'},200),
                             ({**good,'acknowledged':True},200),(good,503)]:
            with self.assertRaises(RecoveryError):
                RecoveryEdgeClient(URL,TOKEN,client_factory=client(payload,code)).exchange('claim',tenant,event)
        with self.assertRaises(RecoveryError):
            edge.exchange('delete',tenant,event)

if __name__=='__main__':unittest.main()
