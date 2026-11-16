"""v1.0: offline rehearsal with invented Garmin-like summaries ONLY."""
import json
import unittest

from garminai_public.identity import DemoIdentityVerifier
from garminai_public.garmin_activity_staging import (
    parse_activity_push, prepare_for_owner, TrustedOwnerBinding,
    UntrustedNotification, integration_status,
)

FAKE = {
    'activities': [
        {'userId':'FAKE_USER_A', 'summaryId':'FAKE_SUMMARY_A1',
         'activityType':'RUNNING', 'startTimeInSeconds':1794650000,
         'durationInSeconds':2400, 'distanceInMeters':7200.0,
         'userAccessToken':'SHOULD_NOT_PERSIST'},
        {'userId':'FAKE_USER_A', 'summaryId':'FAKE_SUMMARY_A2',
         'activityType':'CYCLING', 'startTimeInSeconds':1794652000,
         'durationInSeconds':3700, 'distanceInMeters':18900.0},
    ]
}


def as_body(obj):
    return json.dumps(obj).encode()


class GarminPushOfflineStaging(unittest.TestCase):
    def setUp(self):
        verifier = DemoIdentityVerifier(b'offline-only-identities-' * 3)
        self.alice = verifier.verify(verifier.issue_for_test('alice'))
        self.bob = verifier.verify(verifier.issue_for_test('bob'))

    def test_normalization_drops_garmin_user_token(self):
        events = parse_activity_push(as_body(FAKE), 'application/json; charset=utf-8')
        self.assertEqual(len(events), 2)
        self.assertNotIn('SHOULD_NOT_PERSIST', repr(events))
        self.assertEqual(events[0].activity_id, 'FAKE_SUMMARY_A1')

    def test_owner_scoped_batch(self):
        items = parse_activity_push(as_body(FAKE), 'application/json')
        a = prepare_for_owner(TrustedOwnerBinding(self.alice, 'FAKE_USER_A'), items)
        b = prepare_for_owner(TrustedOwnerBinding(self.bob, 'FAKE_USER_A'), items)
        self.assertEqual(a.subject, 'alice')
        self.assertEqual(b.subject, 'bob')
        self.assertNotEqual(a.event_fingerprints, b.event_fingerprints)
        self.assertNotIn('SHOULD_NOT_PERSIST', repr(a))

    def test_reject_unbound_foreign_user(self):
        items = parse_activity_push(as_body(FAKE), 'application/json')
        with self.assertRaises(PermissionError):
            prepare_for_owner(TrustedOwnerBinding(self.bob, 'FAKE_USER_B'), items)

    def test_one_foreign_record_rejects_entire_batch(self):
        fake = json.loads(json.dumps(FAKE))
        fake['activities'][1]['userId'] = 'FAKE_USER_B'
        items = parse_activity_push(as_body(fake), 'application/json')
        with self.assertRaises(PermissionError):
            prepare_for_owner(TrustedOwnerBinding(self.alice, 'FAKE_USER_A'), items)

    def test_duplicate_same_record_ignored(self):
        fake = {'activities':[FAKE['activities'][0], FAKE['activities'][0]]}
        items = parse_activity_push(as_body(fake), 'application/json')
        batch = prepare_for_owner(TrustedOwnerBinding(self.alice,'FAKE_USER_A'), items)
        self.assertEqual(len(batch.events), 1)
        self.assertEqual(batch.duplicate_count, 1)

    def test_conflicting_duplicate_is_error(self):
        changed = dict(FAKE['activities'][0], durationInSeconds=2500)
        items = parse_activity_push(as_body({'activities':[FAKE['activities'][0], changed]}), 'application/json')
        with self.assertRaises(UntrustedNotification):
            prepare_for_owner(TrustedOwnerBinding(self.alice,'FAKE_USER_A'), items)

    def test_reject_malicious_or_unreviewed_shapes(self):
        cases = [
            (b'{}','application/json'), (b'[]','application/json'),
            (b'{"activities":[],"activityDetails":[]}', 'application/json'),
            (b'{"activities":[{}]}','application/json'),
            (b'{"activities":[{"userId":"x","userId":"y"}]}','application/json'),
            (b'{"activities":[{"userId":"x","summaryId":"y","activityType":"RUNNING","startTimeInSeconds":0,"durationInSeconds":NaN}]}','application/json'),
            (as_body(FAKE), 'text/plain'),
            (b'X'*512001,'application/json'),
        ]
        for raw, content_type in cases:
            with self.subTest(raw=raw[:30], content_type=content_type):
                with self.assertRaises(UntrustedNotification):
                    parse_activity_push(raw, content_type)

    def test_reject_boolean_numeric_values(self):
        fake = json.loads(json.dumps(FAKE))
        fake['activities'][0]['startTimeInSeconds'] = True
        with self.assertRaises(UntrustedNotification):
            parse_activity_push(as_body(fake),'application/json')

    def test_no_real_ingestion_even_with_flag(self):
        status = integration_status({'GARMINAI_GARMIN_PUSH_ENABLED':'1'})
        self.assertFalse(status['oauth_connect_enabled'])
        self.assertFalse(status['push_ingestion_enabled'])
        self.assertFalse(status['mcp_real_garmin_data_enabled'])


if __name__ == '__main__':
    unittest.main()

class GarminLiveRoutesFailClosed(unittest.TestCase):
    def test_routes_registered_before_public_mcp_mount_and_disabled(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'garminai_public/http_server.py').read_text()
        for path in [
            '/garmin/push/activities', '/garmin/push/activity-details',
            '/garmin/push/activity-files', '/garmin/push/manually-updated',
            '/garmin/push/moveiq', '/garmin/push/deregistrations',
            '/garmin/push/permissions-change',
        ]:
            with self.subTest(path=path):
                self.assertIn('Route("' + path + '", garmin_push_disabled, methods=["POST"])', source)
        self.assertLess(source.index('Route("/garmin/push/activities"'),
                        source.index('Mount("/", app=DemoBearerGate'))
        guard_source = (Path(__file__).resolve().parents[1] / 'garminai_public/garmin_http_staging.py').read_text()
        fn_body = guard_source.split('async def garmin_push_disabled(_request):', 1)[1]
        self.assertIn('status_code=503', fn_body)
        self.assertNotIn('request.body', fn_body)
        self.assertNotIn('status_code=200', fn_body)

    def test_callback_remains_disabled(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'garminai_public/http_server.py').read_text()
        fn_body = source.split('async def garmin_callback_disabled(_request):', 1)[1].split('\n@asynccontextmanager', 1)[0]
        self.assertIn('status_code=503', fn_body)

class GarminHttpStagingContract(unittest.TestCase):
    def test_real_starlette_http_responses(self):
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.testclient import TestClient
        from garminai_public.garmin_http_staging import garmin_push_disabled, garmin_integration_status
        app = Starlette(routes=[
            Route('/garmin/integration/status', garmin_integration_status),
            Route('/garmin/push/activities', garmin_push_disabled, methods=['POST']),
        ])
        with TestClient(app) as client:
            r = client.get('/garmin/integration/status')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()['version'], '1.1.8')
            self.assertIs(r.json()['push_ingestion_enabled'], False)
            self.assertEqual(r.headers['cache-control'], 'no-store')
            r = client.post('/garmin/push/activities', json=FAKE)
            self.assertEqual(r.status_code, 503)
            self.assertEqual(r.json()['error'], 'garmin_push_not_enabled')
            self.assertEqual(r.headers['cache-control'], 'no-store')
            self.assertEqual(client.get('/garmin/push/activities').status_code, 405)
