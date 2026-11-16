"""v1.1.7 public diagnostics remain read-only and never authorize Garmin pushes."""
import unittest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from garminai_public.garmin_edge_to_neon_status_v117 import bridge_status, public_bridge_status
from garminai_public.garmin_http_staging import garmin_push_disabled

class BridgePublicStatusTests(unittest.TestCase):
    def test_disabled_by_default_no_values_secrets_or_network(self):
        s=bridge_status({})
        self.assertEqual(s['version'],'1.1.7')
        self.assertFalse(s['operator_enabled'])
        self.assertFalse(s['live_garmin_push_enabled'])
        self.assertTrue(s['no_public_render_bridge_post_route'])
        self.assertEqual(s['production_readiness'],'BLOCKED')
        self.assertNotIn('LAB_TOKEN',str(s))
        self.assertNotIn('BRIDGE_TOKEN',str(s))
    def test_opt_in_does_not_turn_on_live_garmin(self):
        s=bridge_status({'GARMINAI_EDGE_BRIDGE_STAGING_ENABLED':'1',
                         'GARMINAI_GARMIN_PUSH_ENABLED':'1',
                         'GARMINAI_EDGE_BRIDGE_TOKEN':'NEVER_REVEAL_ME'})
        self.assertTrue(s['operator_enabled'])
        self.assertFalse(s['live_garmin_push_enabled'])
        self.assertNotIn('NEVER_REVEAL_ME',str(s))
    def test_public_route_get_only(self):
        app=Starlette(routes=[Route('/garmin/ingress/edge-to-neon',public_bridge_status),
            Route('/garmin/push/activities',garmin_push_disabled,methods=['POST'])])
        with TestClient(app) as c:
            r=c.get('/garmin/ingress/edge-to-neon')
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.headers['cache-control'],'no-store')
            self.assertEqual(r.json()['production_readiness'],'BLOCKED')
            self.assertEqual(c.post('/garmin/ingress/edge-to-neon').status_code,405)
            self.assertEqual(c.post('/garmin/push/activities',json={'activities':[]}).status_code,503)
if __name__=='__main__':unittest.main()
