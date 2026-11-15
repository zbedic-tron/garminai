"""v1.1.2: mock persistence and zero Garmin calls; factual online test remains opt-in."""
import unittest
from garminai_public.identity import DemoIdentityVerifier
from garminai_public.garmin_push_e2e_v112 import (
    CONFIRM, FIXTURE_ID, rehearse_for_verified_principal,
)
from garminai_public.garmin_push_inbox_v111 import OfflinePostgresPushInbox
from test_garmin_push_inbox_v111 import FakePg, DB


class EndToEndRehearsalTest(unittest.TestCase):
    def setUp(self):
        signer=DemoIdentityVerifier(b'fake-signing-key-for-tests-only-123456789')
        self.alice=signer.verify(signer.issue_for_test('alice'))
        self.bob=signer.verify(signer.issue_for_test('bob'))
        self.db=FakePg()
        self.store=OfflinePostgresPushInbox(DB, connection_factory=self.db.connect)
        self.env={'GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED':'1'}

    def run_for(self, who, confirmation=CONFIRM, **kwargs):
        return rehearse_for_verified_principal(who,confirmation,env=self.env,
            lookup=lambda p: self.db.link.get(p.subject),store=self.store,**kwargs)

    def test_disabled_does_not_create_row(self):
        self.env.clear()
        result=self.run_for(self.alice)
        self.assertEqual(result['status'],'OPERATOR_DISABLED')
        self.assertFalse(self.db.inbox)

    def test_requires_explicit_confirmation(self):
        r=self.run_for(self.alice,'no')
        self.assertEqual(r['status'],'CONFIRMATION_REQUIRED')
        self.assertEqual(r['required'],CONFIRM)
        self.assertEqual(self.db.inbox,{})

    def test_rehearsal_commits_and_replays_one_synthetic_record(self):
        r=self.run_for(self.alice)
        self.assertEqual(r['status'],'PASS')
        self.assertEqual(r['persistent_fixture_limit_per_subject'],1)
        self.assertEqual(self.run_for(self.alice)['status'],'PASS')
        self.assertEqual(list(self.db.inbox),[('alice',FIXTURE_ID)])
        saved=repr(self.db.inbox)
        self.assertNotIn('GARMIN_A',saved)
        self.assertNotIn('userAccessToken',saved)
        self.assertNotIn('gps',saved.lower())
        self.assertFalse(r['real_activities_read'])

    def test_two_users_are_disjoint(self):
        self.assertEqual(self.run_for(self.alice)['status'],'PASS')
        self.assertEqual(self.run_for(self.bob)['status'],'PASS')
        self.assertEqual(set(self.db.inbox),{('alice', FIXTURE_ID),('bob', FIXTURE_ID)})

    def test_link_required(self):
        self.db.link.pop('alice')
        self.assertEqual(self.run_for(self.alice)['status'],'GARMIN_LINK_REQUIRED')
        self.assertFalse(self.db.inbox)

    def test_owner_proof_is_checked_again_inside_transaction(self):
        # Fake lookup lies; store's own RLS-associated verified Garmin identity rejects.
        r=rehearse_for_verified_principal(self.alice,CONFIRM,env=self.env,
            lookup=lambda _: 'GARMIN_B',store=self.store)
        self.assertEqual(r['status'],'CHECK_FAILED')
        self.assertFalse(self.db.inbox)

    def test_db_error_is_redacted(self):
        class Broken:
            def enqueue_offline_verified_fixture(self,*_):
                raise RuntimeError('db-password-must-never-be-shown')
        r=rehearse_for_verified_principal(self.alice,CONFIRM,env=self.env,
            lookup=lambda _: 'GARMIN_A',store=Broken())
        self.assertEqual(r,{'status':'STORAGE_NOT_READY'})

    def test_invalid_principal_rejected(self):
        self.assertEqual(rehearse_for_verified_principal('alice',CONFIRM,
            env=self.env,lookup=lambda _: 'GARMIN_A',store=self.store),
            {'status':'NEON_AUTH_REQUIRED'})

if __name__ == '__main__':
    unittest.main()
