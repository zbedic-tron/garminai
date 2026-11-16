import unittest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient
from garminai_public.garmin_delivery_recovery_status_v118 import recovery_status, public_recovery_status
from garminai_public.garmin_http_staging import garmin_push_disabled

class ReadOnlyRecoveryStatusTests(unittest.TestCase):
    def test_static_config_only(self):
        disabled=recovery_status({})
        self.assertFalse(disabled['operator_enabled'])
        self.assertFalse(disabled['garmin_live_push_enabled'])
        self.assertFalse(disabled['automatic_background_delivery_enabled'])
        self.assertEqual(disabled['production_readiness'],'BLOCKED')
        enabled=recovery_status({'GARMINAI_EDGE_RECOVERY_STAGING_ENABLED':'1',
                                 'GARMINAI_EDGE_BRIDGE_TOKEN':'REDACTED_SECRET_XYZ'})
        self.assertTrue(enabled['operator_enabled'])
        self.assertNotIn('REDACTED_SECRET_XYZ',str(enabled))
        self.assertFalse(enabled['remote_recovery_flow_verified_by_this_diagnostic'])

    def test_get_only_and_live_push_stays_disabled(self):
        app=Starlette(routes=[Route('/garmin/ingress/delivery-recovery',public_recovery_status),
                             Route('/garmin/push/activities',garmin_push_disabled,methods=['POST'])])
        with TestClient(app) as client:
            r=client.get('/garmin/ingress/delivery-recovery')
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.headers.get('cache-control'),'no-store')
            self.assertEqual(r.json()['version'],'1.1.8')
            self.assertEqual(client.post('/garmin/ingress/delivery-recovery').status_code,405)
            self.assertEqual(client.post('/garmin/push/activities',json={'activities':[]}).status_code,503)

if __name__=='__main__':unittest.main()
