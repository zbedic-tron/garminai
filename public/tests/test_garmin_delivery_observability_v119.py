"""v1.1.9 synthetic-only read observability and guarded manual retry tests."""
import unittest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from garminai_public.identity import DemoIdentityVerifier
from garminai_public.garmin_push_inbox_v111 import OfflinePostgresPushInbox
from garminai_public.garmin_delivery_recovery_v118 import (
    rehearse_for_principal, recipient_for_recovery,
)
from garminai_public.garmin_delivery_observability_v119 import (
    observe_for_principal, manual_retry_for_principal, CONFIRM,
    MAX_MANUAL_ATTEMPTS, OPERATOR_FLAG,
)
from garminai_public.garmin_delivery_observability_status_v119 import (
    observability_status, public_observability_status,
)
from garminai_public.garmin_http_staging import garmin_push_disabled
from test_garmin_delivery_recovery_v118 import FakeRecoveryEdge, FakePg, DB, TOKEN, URL


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        verifier = DemoIdentityVerifier(b'test-signer-test-signer-test-signer-1')
        self.a = verifier.verify(verifier.issue_for_test('alice'))
        self.b = verifier.verify(verifier.issue_for_test('bob'))
        self.db = FakePg()
        self.store = OfflinePostgresPushInbox(DB, connection_factory=self.db.connect)
        self.edge = FakeRecoveryEdge(self.db)
        self.env = {
            'GARMINAI_EDGE_BRIDGE_URL': URL,
            'GARMINAI_EDGE_BRIDGE_TOKEN': TOKEN,
            'GARMINAI_EDGE_RECOVERY_STAGING_ENABLED': '0',
            OPERATOR_FLAG: '0',
        }

    def status(self, principal=None):
        return observe_for_principal(principal or self.a, env=self.env, edge=self.edge)

    def retry(self, principal=None, confirmation=CONFIRM):
        return manual_retry_for_principal(principal or self.a, confirmation,
            env=self.env, edge=self.edge,
            lookup=lambda p: self.db.link.get(p.subject), store=self.store)

    def seed(self, principal=None):
        return rehearse_for_principal(principal or self.a,
            'RUN_SYNTHETIC_DELIVERY_RECOVERY', 'SIMULATE_RENDER_DELAY',
            env={**self.env, 'GARMINAI_EDGE_RECOVERY_STAGING_ENABLED': '1'},
            edge=self.edge, lookup=lambda p: self.db.link.get(p.subject), store=self.store)

    def test_read_only_no_record_and_no_side_effect(self):
        self.assertEqual(self.status()['status'],'NOT_STARTED')
        self.assertFalse(self.status()['retry_permitted'])
        self.assertFalse(self.edge.receipts)
        self.assertFalse(self.db.inbox)

    def test_confirm_and_operator_disable_precedes_any_write(self):
        self.assertEqual(self.retry()['status'],'OPERATOR_DISABLED')
        self.env[OPERATOR_FLAG]='1'
        self.assertEqual(self.retry(confirmation='INVALID')['status'],'CONFIRMATION_REQUIRED')
        self.assertEqual(self.retry()['status'],'NOT_STARTED')
        self.assertFalse(self.db.inbox)

    def test_pending_retry_commit_ack_is_idempotent(self):
        self.assertEqual(self.seed()['status'],'SIMULATED_RENDER_DELAY_D1_PENDING')
        before = self.status()
        self.assertEqual(before['d1_claim_attempts'],0)
        self.assertFalse(before['retry_permitted'])
        self.env[OPERATOR_FLAG]='1'
        self.assertTrue(self.status()['retry_permitted'])
        self.assertEqual(self.status()['remaining_manual_attempts'],MAX_MANUAL_ATTEMPTS)
        result = self.retry()
        self.assertEqual(result['status'],'PASS')
        self.assertTrue(result['d1_acknowledged'])
        self.assertTrue(result['neon_duplicate_prevented'])
        self.assertEqual(len(self.db.inbox),1)
        count=len(self.edge.calls)
        again = self.retry()
        self.assertEqual(again['status'],'ALREADY_ACKNOWLEDGED')
        self.assertFalse(again['retry_performed'])
        self.assertEqual(len(self.edge.calls),count+1) # read-only inspection, no claim
        self.assertEqual(len(self.db.inbox),1)
        self.assertEqual(self.status()['attention'],'NONE')

    def test_ack_failure_still_retryable_and_deduplicated(self):
        self.seed()
        self.env[OPERATOR_FLAG]='1'
        self.edge.ack_fail=True
        self.assertEqual(self.retry()['status'],'MANUAL_RETRY_NOT_CONFIRMED')
        self.assertEqual(len(self.db.inbox),1)
        self.assertEqual(self.status()['delivery_state'],'PENDING_SYNTHETIC')
        self.edge.ack_fail=False
        self.assertEqual(self.retry()['status'],'PASS')
        self.assertEqual(len(self.db.inbox),1)

    def test_retry_budget_applies_without_resetting_d1(self):
        self.seed()
        self.env[OPERATOR_FLAG]='1'
        receipt=self.edge.receipts[recipient_for_recovery(self.a,TOKEN)]
        receipt['attempts']=MAX_MANUAL_ATTEMPTS
        self.assertEqual(self.status()['attention'],'MANUAL_ATTEMPT_LIMIT_REACHED')
        self.assertFalse(self.status()['retry_permitted'])
        calls=len(self.edge.calls)
        self.assertEqual(self.retry()['status'],'MANUAL_ATTEMPT_LIMIT_REACHED')
        self.assertEqual(len(self.edge.calls),calls+1) # only inspect
        self.assertFalse(self.db.inbox)

    def test_link_missing_remains_pending_never_ack(self):
        self.seed()
        self.env[OPERATOR_FLAG]='1'
        self.db.link.pop('alice')
        self.assertEqual(self.retry()['status'],'MANUAL_RETRY_NOT_CONFIRMED')
        self.assertFalse(self.status()['d1_acknowledged'])

    def test_per_subject_isolation_and_no_sensitive_fields(self):
        self.seed(self.a)
        self.assertEqual(self.status(self.b)['status'],'NOT_STARTED')
        self.env[OPERATOR_FLAG]='1'
        self.assertEqual(self.retry(self.a)['status'],'PASS')
        self.assertEqual(self.status(self.b)['status'],'NOT_STARTED')
        response=str(self.status(self.a))
        for secret in (TOKEN,'alice','bob','GARMIN_A','SYNTHETIC_RECOVERY_V118_'):
            self.assertNotIn(secret,response)
        self.assertFalse(self.status(self.a)['historical_latency_available'])
        self.assertEqual(self.status(self.a)['last_failure_code'],'NOT_RECORDED_IN_V118_SCHEMA')

    def test_error_or_wrong_principal_is_safe(self):
        self.assertEqual(observe_for_principal(None,env=self.env)['status'],'NEON_AUTH_REQUIRED')
        self.assertEqual(manual_retry_for_principal(None,CONFIRM,env=self.env)['status'],'NEON_AUTH_REQUIRED')
        bad={**self.env,'GARMINAI_EDGE_BRIDGE_URL':'http://127.0.0.1'}
        self.assertEqual(observe_for_principal(self.a,env=bad)['status'],'OBSERVABILITY_UNAVAILABLE')
        self.assertFalse(observe_for_principal(self.a,env=bad)['retry_permitted'])

    def test_public_diagnostic_never_exposes_subject(self):
        config=observability_status({OPERATOR_FLAG:'1', 'GARMINAI_EDGE_BRIDGE_TOKEN':'MY_SECRET'})
        self.assertEqual(config['version'],'1.1.9')
        self.assertEqual(config['production_readiness'],'BLOCKED')
        self.assertFalse(config['automatic_background_retry_enabled'])
        self.assertNotIn('MY_SECRET',str(config))
        app=Starlette(routes=[Route('/garmin/ingress/delivery-observability',public_observability_status),
                              Route('/garmin/push/activities',garmin_push_disabled,methods=['POST'])])
        with TestClient(app) as client:
            r=client.get('/garmin/ingress/delivery-observability')
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.headers['cache-control'],'no-store')
            self.assertEqual(r.json()['production_readiness'],'BLOCKED')
            self.assertEqual(client.post('/garmin/ingress/delivery-observability').status_code,405)
            self.assertEqual(client.post('/garmin/push/activities',json={'activities':[]}).status_code,503)

if __name__=='__main__':
    unittest.main()
