"""Synthetic Garmin data only; fake PostgreSQL, no external API or personal data."""
import copy
import json
import unittest

from garminai_public.identity import DemoIdentityVerifier
from garminai_public.garmin_activity_staging import parse_activity_push, prepare_for_owner, TrustedOwnerBinding
from garminai_public.garmin_push_inbox_v111 import OfflinePostgresPushInbox
from garminai_public.garmin_push_rehearsal_v110 import (
    PushStorageUnavailable, PushOwnershipRejected, PushConflictingReplay,
)
from garminai_public.garmin_sender_review_v111 import review_asgi_source, offline_acknowledgement_candidate

DB = 'postgresql://garminai_app:fake@localhost/demo?sslmode=require'


def fixture(uid='GARMIN_A', aid='SYNTH_1', dist=4000.0):
    return {'userId': uid, 'summaryId': aid, 'activityType': 'RUNNING',
            'startTimeInSeconds': 1794650000, 'durationInSeconds': 1200,
            'distanceInMeters': dist, 'userAccessToken': 'NEVER_WRITE_THIS',
            'startingLatitudeInDegree': 46.0}


class FakePg:
    def __init__(self):
        self.role = 'garminai_app'
        self.rls = True
        self.migrated = True
        self.link = {'alice': 'GARMIN_A', 'bob': 'GARMIN_B'}
        self.credentials = {'alice', 'bob'}
        self.inbox = {}

    def connect(self, _):
        return Ctx(self)


class Ctx:
    def __init__(self, db):
        self.db = db
        self.pending = None
        self.subject = None
        self.rows = []
        self.one = None

    def __enter__(self):
        self.pending = copy.deepcopy(self.db.inbox)
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.db.inbox = self.pending

    def cursor(self):
        return self

    def execute(self, query, params=None):
        q = ' '.join(query.lower().split())
        self.rows, self.one = [], None
        if q.startswith('select current_user'):
            self.one = (self.db.role,)
        elif "select set_config('garminai.subject'" in q:
            self.subject = params[0]
            self.one = (self.subject,)
        elif 'from pg_class' in q:
            names = ['athletes', 'garmin_credentials', 'garmin_push_inbox']
            if not self.db.migrated: names.remove('garmin_push_inbox')
            self.rows = [(x, self.db.rls, self.db.rls) for x in names]
        elif 'select garmin_user_id from garminai.athletes' in q:
            value = self.db.link.get(self.subject)
            self.one = (value,) if value else None
        elif 'select 1 from garminai.garmin_credentials' in q:
            self.one = (1,) if self.subject in self.db.credentials else None
        elif q.startswith('insert into garminai.garmin_push_inbox'):
            subject, aid, digest, payload = params
            assert subject == self.subject
            key = (subject, aid)
            if key not in self.pending:
                self.pending[key] = (digest, json.loads(payload))
                self.one = (digest,)
        elif q.startswith('select payload_sha256,summary from garminai.garmin_push_inbox'):
            subject, aid = params
            assert subject == self.subject
            self.one = self.pending.get((subject,aid))
        else:
            raise AssertionError('Unexpected SQL query: ' + q[:120])

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows


class InboxRehearsalTest(unittest.TestCase):
    def setUp(self):
        signer = DemoIdentityVerifier(b'not-a-production-verifier--' * 2)
        self.alice = signer.verify(signer.issue_for_test('alice'))
        self.bob = signer.verify(signer.issue_for_test('bob'))
        self.db = FakePg()
        self.store = OfflinePostgresPushInbox(DB, connection_factory=self.db.connect)

    def batch(self, who, user, rows):
        binding = TrustedOwnerBinding(who,user)
        raw = json.dumps({'activities': rows}).encode()
        return binding, prepare_for_owner(binding,parse_activity_push(raw,'application/json'))

    def test_enqueue_and_duplicate(self):
        binding,batch = self.batch(self.alice,'GARMIN_A',[fixture()])
        a = self.store.enqueue_offline_verified_fixture(binding,batch)
        b = self.store.enqueue_offline_verified_fixture(binding,batch)
        self.assertEqual((a.enqueued,a.duplicates),(1,0))
        self.assertEqual((b.enqueued,b.duplicates),(0,1))
        self.assertEqual(len(self.db.inbox),1)
        saved = str(self.db.inbox)
        self.assertNotIn('NEVER_WRITE_THIS',saved)
        self.assertNotIn('GARMIN_A',saved)
        self.assertNotIn('startingLatitude',saved)

    def test_two_separate_subjects(self):
        for who,user in ((self.alice,'GARMIN_A'),(self.bob,'GARMIN_B')):
            b,bt = self.batch(who,user,[fixture(user)])
            self.store.enqueue_offline_verified_fixture(b,bt)
        self.assertEqual(len(self.db.inbox),2)
        self.assertEqual({k[0] for k in self.db.inbox}, {'alice','bob'})

    def test_cross_user_link_rejected(self):
        binding,batch = self.batch(self.alice,'GARMIN_A',[fixture()])
        self.db.link['alice']='GARMIN_B'
        with self.assertRaises(PushOwnershipRejected):
            self.store.enqueue_offline_verified_fixture(binding,batch)
        self.assertEqual(self.db.inbox,{})

    def test_missing_credentials_rejected(self):
        binding,batch = self.batch(self.alice,'GARMIN_A',[fixture()])
        self.db.credentials.remove('alice')
        with self.assertRaises(PushOwnershipRejected):
            self.store.enqueue_offline_verified_fixture(binding,batch)

    def test_conflicting_replay_rollback_whole_batch(self):
        b,bt = self.batch(self.alice,'GARMIN_A',[fixture()])
        self.store.enqueue_offline_verified_fixture(b,bt)
        b2,bt2 = self.batch(self.alice,'GARMIN_A',[fixture(aid='NEW'), fixture(dist=999.0)])
        with self.assertRaises(PushConflictingReplay):
            self.store.enqueue_offline_verified_fixture(b2,bt2)
        self.assertEqual(len(self.db.inbox),1)
        self.assertNotIn(('alice','NEW'),self.db.inbox)

    def test_migration_role_rls_checked(self):
        b,bt = self.batch(self.alice,'GARMIN_A',[fixture()])
        for prop, value in (('role','owner'),('rls',False),('migrated',False)):
            old = getattr(self.db,prop)
            setattr(self.db,prop,value)
            with self.assertRaises(PushStorageUnavailable):
                self.store.enqueue_offline_verified_fixture(b,bt)
            setattr(self.db,prop,old)
        self.assertEqual(self.db.inbox,{})


class SenderReviewTest(unittest.TestCase):
    RANGES = ('203.0.113.0/24',)  # RFC 5737 synthetic test network, NOT Garmin IPs

    def test_matching_socket_ip_is_not_authenticated(self):
        result = review_asgi_source({'client': ('203.0.113.6', 51234)}, [], self.RANGES)
        self.assertTrue(result.matches_reference_range)
        self.assertFalse(result.sender_authenticated)

    def test_spoofed_forwarded_headers_cannot_authenticate(self):
        for name in (b'x-forwarded-for', b'cf-connecting-ip', b'true-client-ip',b'forwarded'):
            result = review_asgi_source({'client': ('198.51.100.10', 2000)},
                                        [(name,b'203.0.113.6')], self.RANGES)
            self.assertTrue(result.proxy_headers_present)
            self.assertFalse(result.matches_reference_range)
            self.assertFalse(result.sender_authenticated)

    def test_invalid_peer_fails_closed(self):
        for peer in (None, ('not-an-ip',123), ('127.0.0.1',42)):
            result=review_asgi_source({'client': peer},[],self.RANGES)
            self.assertFalse(result.sender_authenticated)
            self.assertFalse(result.matches_reference_range)

    def test_ack_requires_all_four_verified_predicates(self):
        ok=dict(verified_ingress=True,verified_owner=True,
                durable_commit=True,payload_validated=True)
        self.assertEqual(offline_acknowledgement_candidate(**ok),200)
        for k in ok:
            bad={**ok,k:False}
            self.assertEqual(offline_acknowledgement_candidate(**bad),503)
        self.assertEqual(offline_acknowledgement_candidate(**{**ok,'durable_commit':1}),503)


if __name__ == '__main__':
    unittest.main()
