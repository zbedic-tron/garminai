"""v1.1.0: offline-only transactional tests. Uses FAKE GARMIN data and FAKE PG."""
import copy
import json
import unittest
from pathlib import Path

from garminai_public.identity import DemoIdentityVerifier
from garminai_public.garmin_activity_staging import (
    parse_activity_push, prepare_for_owner, TrustedOwnerBinding,
)
from garminai_public.garmin_push_rehearsal_v110 import (
    PostgresPushRehearsalStore, PushOwnershipRejected, PushStorageUnavailable,
    PushConflictingReplay, normalized_summary,
)

DB_URL = 'postgresql://garminai_app:fake@localhost/test?sslmode=require'


def sample(user='GARMIN_A', aid='DEMO_1', dist=5000.0):
    return {'userId': user, 'summaryId': aid, 'activityType': 'RUNNING',
            'startTimeInSeconds': 1794650000, 'durationInSeconds': 1800,
            'distanceInMeters': dist, 'userAccessToken': 'NEVER_KEEP_THIS'}


class FakePG:
    def __init__(self):
        self.athletes = {}
        self.credentials = set()
        self.activities = {}
        self.receipts = {}
        self.missing_table = False
        self.rls_disabled = False
        self.role = 'garminai_app'
        self.force_receipt_conflict = False

    def connect(self, _url):
        return FakeConnection(self)


class FakeConnection:
    def __init__(self, db):
        self.db = db
        self.pending = None

    def __enter__(self):
        self.pending = (copy.deepcopy(self.db.activities), copy.deepcopy(self.db.receipts))
        return self

    def __exit__(self, typ, value, traceback):
        if typ is None:
            self.db.activities, self.db.receipts = self.pending
        self.pending = None

    def cursor(self):
        return FakeCursor(self)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.db = conn.db
        self.one = None
        self.rows = None
        self.subject = None

    def __enter__(self): return self
    def __exit__(self, *_): pass
    def fetchone(self): return self.one
    def fetchall(self): return self.rows

    def execute(self, sql, params=()):
        txt = ' '.join(sql.split()).lower()
        self.one = None
        self.rows = None
        if txt == 'select current_user':
            self.one = (self.db.role,)
        elif txt.startswith("select set_config('garminai.subject'"):
            self.subject = params[0]
            self.one = (self.subject,)
        elif 'from pg_class c' in txt:
            names = ['athletes','activities','garmin_credentials','garmin_push_receipts']
            self.rows = [(n, True, not self.db.rls_disabled) for n in names if not (n == 'garmin_push_receipts' and self.db.missing_table)]
        elif 'from garminai.athletes' in txt:
            self.one = (self.db.athletes[self.subject],) if self.subject in self.db.athletes else None
        elif txt.startswith('select 1 from garminai.garmin_credentials'):
            self.one = (1,) if self.subject in self.db.credentials else None
        elif txt.startswith('insert into garminai.activities'):
            subject, aid, start_time, payload = params
            assert subject == self.subject
            key = subject, aid
            if key not in self.conn.pending[0]:
                self.conn.pending[0][key] = json.loads(payload)
                self.one = (aid,)
        elif txt.startswith('select summary from garminai.activities'):
            key = params[0], params[1]
            stored = self.conn.pending[0].get(key)
            self.one = (stored,) if stored is not None else None
        elif txt.startswith('insert into garminai.garmin_push_receipts'):
            subject, aid, digest = params
            assert subject == self.subject
            key = subject, aid
            if key not in self.conn.pending[1]:
                self.conn.pending[1][key] = digest
                self.one = (digest,)
        elif txt.startswith('select payload_sha256 from garminai.garmin_push_receipts'):
            key = params[0], params[1]
            existing = self.conn.pending[1].get(key)
            self.one = (existing,) if existing else None
        else:
            raise AssertionError('Unexpected SQL: ' + txt[:150])


class DurableGarminPushRehearsal(unittest.TestCase):
    def setUp(self):
        signer = DemoIdentityVerifier(b'not-a-production-verifier--' * 2)
        self.alice = signer.verify(signer.issue_for_test('alice'))
        self.bob = signer.verify(signer.issue_for_test('bob'))
        self.db = FakePG()
        self.db.athletes = {'alice': 'GARMIN_A', 'bob': 'GARMIN_B'}
        self.db.credentials = {'alice','bob'}
        self.store = PostgresPushRehearsalStore(DB_URL, connection_factory=self.db.connect)

    def batch(self, principal, user='GARMIN_A', events=None):
        events = events or [sample(user)]
        raw = json.dumps({'activities': events}).encode()
        binding = TrustedOwnerBinding(principal, user)
        return binding, prepare_for_owner(binding, parse_activity_push(raw,'application/json'))

    def test_atomic_insert_and_idempotent_retry(self):
        binding, batch = self.batch(self.alice)
        first = self.store.persist_offline_verified_fixture(binding, batch)
        second = self.store.persist_offline_verified_fixture(binding, batch)
        self.assertEqual((first.inserted,first.duplicate),(1,0))
        self.assertEqual((second.inserted,second.duplicate),(0,1))
        self.assertEqual(len(self.db.activities),1)
        self.assertEqual(len(self.db.receipts),1)
        self.assertNotIn('NEVER_KEEP_THIS',str(self.db.activities))
        self.assertNotIn('GARMIN_A',str(self.db.activities))

    def test_two_tenants_no_cross_read(self):
        a,batch_a = self.batch(self.alice)
        b,batch_b = self.batch(self.bob,'GARMIN_B')
        self.store.persist_offline_verified_fixture(a,batch_a)
        self.store.persist_offline_verified_fixture(b,batch_b)
        self.assertEqual(len(self.db.activities),2)
        self.assertEqual({k[0] for k in self.db.activities},{'alice','bob'})
        self.assertNotEqual(self.db.receipts[('alice','DEMO_1')], self.db.receipts[('bob','DEMO_1')])
        with self.assertRaises(PushOwnershipRejected):
            self.store.persist_offline_verified_fixture(a,batch_b)

    def test_refuse_foreign_link_and_roll_back(self):
        binding,batch = self.batch(self.alice)
        self.db.athletes['alice']='GARMIN_REPLACED'
        with self.assertRaises(PushOwnershipRejected):
            self.store.persist_offline_verified_fixture(binding,batch)
        self.assertEqual(self.db.activities,{})
        self.assertEqual(self.db.receipts,{})

    def test_refuse_missing_credentials(self):
        binding,batch = self.batch(self.alice)
        self.db.credentials.remove('alice')
        with self.assertRaises(PushOwnershipRejected):
            self.store.persist_offline_verified_fixture(binding,batch)

    def test_conflicting_same_id_rolls_back_everything(self):
        binding,batch = self.batch(self.alice)
        self.store.persist_offline_verified_fixture(binding,batch)
        second_binding, changed_batch = self.batch(self.alice,events=[sample(aid='DEMO_2'),sample(dist=4500.0)])
        with self.assertRaises(PushConflictingReplay):
            self.store.persist_offline_verified_fixture(second_binding,changed_batch)
        self.assertNotIn(('alice','DEMO_2'),self.db.activities)
        self.assertEqual(len(self.db.activities),1)
        self.assertEqual(len(self.db.receipts),1)

    def test_fail_closed_missing_migration_and_rls(self):
        binding,batch = self.batch(self.alice)
        for change in ['missing_table','rls_disabled']:
            setattr(self.db,change,True)
            with self.assertRaises(PushStorageUnavailable):
                self.store.persist_offline_verified_fixture(binding,batch)
            setattr(self.db,change,False)
        self.assertFalse(self.db.activities)

    def test_fail_closed_admin_role(self):
        binding,batch = self.batch(self.alice)
        self.db.role='neondb_owner'
        with self.assertRaises(PushStorageUnavailable):
            self.store.persist_offline_verified_fixture(binding,batch)

    def test_cannot_forge_batch_subject(self):
        from dataclasses import replace
        binding,batch = self.batch(self.alice)
        forged = replace(batch,subject='bob')
        with self.assertRaises(PushOwnershipRejected):
            self.store.persist_offline_verified_fixture(binding,forged)
        forged = replace(batch,duplicate_count=99)
        with self.assertRaises(PushOwnershipRejected):
            self.store.persist_offline_verified_fixture(binding,forged)

    def test_forbid_real_push_and_ai_sharing(self):
        from pathlib import Path
        from garminai_public.garmin_activity_staging import integration_status
        root = Path(__file__).resolve().parents[1]
        route = (root/'garminai_public/http_server.py').read_text()
        self.assertIn('garmin_push_disabled, methods=["POST"]',route)
        self.assertNotIn('PostgresPushRehearsalStore',route)
        self.assertFalse(integration_status()['push_ingestion_enabled'])
        self.assertFalse(integration_status()['mcp_real_garmin_data_enabled'])
        sql=(root/'sql/004_garmin_activity_push_rehearsal.sql').read_text()
        self.assertIn('FORCE ROW LEVEL SECURITY',sql)
        self.assertIn('GRANT SELECT, INSERT',sql)
        self.assertNotIn('GRANT SELECT, INSERT, UPDATE',sql)


if __name__=='__main__':
    unittest.main()
