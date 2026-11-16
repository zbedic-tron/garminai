"""v1.1.7 still never opens production intake; edge lab is external OFFLINE source only."""
import unittest
from pathlib import Path
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from garminai_public.garmin_edge_lab_v115 import edge_lab_status, public_edge_lab_status
from garminai_public.garmin_push_readiness_v114 import readiness_report
from garminai_public.garmin_http_staging import garmin_push_disabled

ROOT=Path(__file__).resolve().parents[1]

class EdgeLabAudit(unittest.TestCase):
    def test_public_contract_is_explicitly_not_deployed_or_real(self):
        s=edge_lab_status()
        self.assertEqual(s['version'],'1.1.7')
        self.assertEqual(s['mode'],'OPTIONAL_REMOTE_SYNTHETIC_EDGE_LAB')
        for key in ('edge_worker_deployed_by_garminai',
                    'edge_lab_handles_real_garmin_push',
                    'production_live_garmin_push_ready',
                    'garmin_sender_authentication_verified',
                    'render_free_cold_start_resolved_in_production'):
            self.assertIs(s[key],False)
        self.assertTrue(s['synthetic_only_payloads'])
        self.assertIn('D1_COMMIT_BEFORE_HTTP_200',s['durable_synthetic_ack_design'])
        self.assertNotIn('DATABASE_URL',str(s))

    def test_edge_lab_is_read_only_even_with_untrusted_headers(self):
        app=Starlette(routes=[
            Route('/garmin/ingress/edge-lab',public_edge_lab_status),
            Route('/garmin/ingress/readiness',lambda _: None),
            Route('/garmin/push/activities',garmin_push_disabled,methods=['POST']),
        ])
        with TestClient(app) as c:
            r=c.get('/garmin/ingress/edge-lab');self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['version'],'1.1.7')
            self.assertEqual(r.headers.get('cache-control'),'no-store')
            self.assertEqual(c.post('/garmin/ingress/edge-lab').status_code,405)
            x=c.post('/garmin/push/activities',headers={'CF-Connecting-IP':'203.0.113.55',
                    'X-Forwarded-For':'203.0.113.55'},json={'activities':[]})
            self.assertEqual(x.status_code,503)
            self.assertEqual(x.json()['error'],'garmin_push_not_enabled')

    def test_no_mutation_or_configuration_can_enable_live_push(self):
        r=readiness_report({'GARMINAI_GARMIN_PUSH_ENABLED':'1',
                            'GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED':'1'})
        self.assertEqual(r['readiness'],'BLOCKED')
        self.assertFalse(r['live_garmin_push_enabled'])
        self.assertIn('RENDER_FREE_COLD_START_DEADLINE_NOT_GUARANTEED',r['blocking_reasons'])

    def test_lab_is_isolated_from_backend_and_has_no_secrets(self):
        worker=(ROOT/'edge_lab_v115/worker.mjs').read_text()
        self.assertIn('NON_SYNTHETIC_DATA_REJECTED',worker)
        self.assertNotIn('garminai-public-demo.onrender.com',worker)
        self.assertNotIn('https://apis.garmin.com',worker)
        self.assertNotIn('GARMIN_CLIENT_SECRET',worker)
        source=(ROOT/'garminai_public/http_server.py').read_text()
        self.assertIn('Route("/garmin/ingress/edge-lab", public_edge_lab_status)',source)
        self.assertIn('"version":"1.1.9"',source)
        for path in ('activities','activity-details','activity-files','manually-updated',
                     'moveiq','deregistrations','permissions-change'):
            self.assertIn('Route("/garmin/push/'+path+'", garmin_push_disabled, methods=["POST"])',source)

if __name__=='__main__':unittest.main()
