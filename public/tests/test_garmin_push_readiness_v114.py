"""v1.1.4 operational audit: no real Garmin data, DB/network or secrets."""
import asyncio
import unittest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from garminai_public.garmin_push_readiness_v114 import readiness_report, public_readiness, BLOCKERS
from garminai_public.garmin_http_staging import garmin_push_disabled
from garminai_public.garmin_sender_review_v111 import (
    review_asgi_source, offline_acknowledgement_candidate,
)


class ReadinessReportTest(unittest.TestCase):
    def test_never_claims_live_readiness(self):
        r = readiness_report({})
        self.assertEqual(r['readiness'], 'BLOCKED')
        self.assertEqual(r['mode'], 'READ_ONLY_DIAGNOSTIC')
        self.assertFalse(r['live_garmin_push_enabled'])
        self.assertFalse(r['trusted_source_provenance_verified'])
        self.assertFalse(r['response_deadline_guaranteed_on_free_hosting'])
        self.assertEqual(len(r['blocking_reasons']), len(BLOCKERS))
        self.assertEqual(r['synthetic_neon_test'],'NOT_RERUN_BY_THIS_DIAGNOSTIC')

    def test_operator_flags_cannot_enable_push(self):
        r = readiness_report({
            'GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED':'1',
            'GARMINAI_GARMIN_PUSH_ENABLED':'1',
            'GARMIN_CLIENT_SECRET':'DO_NOT_DISCLOSE_FAKE_SECRET',
            'DATABASE_URL':'DO_NOT_DISCLOSE_FAKE_PASSWORD',
        })
        self.assertTrue(r['rehearsal_flag_should_be_disabled_after_test'])
        self.assertTrue(r['live_push_requested_by_legacy_flag'])
        self.assertTrue(r['legacy_flag_does_not_enable_push'])
        self.assertFalse(r['live_garmin_push_enabled'])
        self.assertNotIn('FAKE_SECRET',str(r))
        self.assertNotIn('FAKE_PASSWORD',str(r))
        self.assertNotIn('DATABASE_URL',str(r))

    def test_no_secret_or_fictional_ip_ranges_in_public_report(self):
        data=str(readiness_report({}))
        for marker in ('X-Forwarded-For', '204.77', 'GARMIN_CLIENT_ID', 'userId',
                       'FOR_UPDATE', 'userAccessToken'):
            self.assertNotIn(marker,data)

    def test_unknown_and_forwarded_ips_never_authenticate(self):
        # Reserved RFC 5737 addresses: not Garmin production sources.
        trusted_looking = '203.0.113.50'
        review=review_asgi_source({'client':(trusted_looking, 1234)},
                                  [(b'x-forwarded-for',b'203.0.113.20')],
                                  ['203.0.113.0/24'])
        self.assertTrue(review.matches_reference_range)
        self.assertFalse(review.sender_authenticated)
        self.assertFalse(offline_acknowledgement_candidate(
            verified_ingress=False,verified_owner=True,
            durable_commit=True,payload_validated=True)==200)


class IngressRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = ('activities','activity-details','activity-files',
                     'manually-updated','moveiq','deregistrations','permissions-change')
        app=Starlette(routes=[
            Route('/garmin/ingress/readiness', public_readiness),
            *[Route('/garmin/push/'+p, garmin_push_disabled,methods=['POST']) for p in cls.paths],
        ])
        cls.client=TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_get_report_is_read_only_and_uncacheable(self):
        response=self.client.get('/garmin/ingress/readiness')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(response.json()['readiness'],'BLOCKED')
        self.assertNotIn('http',response.json()['mode'].lower())

    def test_all_public_push_routes_fail_closed_even_with_spoofed_headers(self):
        fake={"activities":[{"userId":"spoof","summaryId":"spoof"}]}
        for suffix in self.paths:
            for headers in ({}, {'X-Forwarded-For':'203.0.113.44',
                                 'CF-Connecting-IP':'203.0.113.44',
                                 'True-Client-IP':'203.0.113.44'},
                            {'Authorization':'Bearer FAKE'}):
                with self.subTest(path=suffix, headers=headers):
                    r=self.client.post('/garmin/push/'+suffix,
                                       headers=headers,json=fake)
                    self.assertEqual(r.status_code,503)
                    self.assertEqual(r.json()['error'],'garmin_push_not_enabled')
                    self.assertEqual(r.headers.get('cache-control'),'no-store')
                    self.assertNotIn('spoof',r.text)

    def test_no_public_write_route_or_stateful_audit(self):
        self.assertEqual(self.client.post('/garmin/ingress/readiness').status_code,405)


if __name__ == '__main__':
    unittest.main()
