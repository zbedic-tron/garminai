import asyncio
import unittest
import httpx
from garminai_public.neon_auth_check import (
    validate_auth_url, auth_configuration_status, check_auth_connection,
)

BASE = 'https://ep-example.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth'

class NeonAuthProbeTests(unittest.TestCase):
    def test_valid_auth_url(self):
        self.assertTrue(validate_auth_url(BASE))
    def test_invalid_urls(self):
        for x in ['http://'+BASE[8:], 'https://foo.com/neondb/auth',
                  'https://evilneon.tech/neondb/auth',
                  'https://someone@ep-example.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth',
                  'https://ep-example.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth?x=1',
                  'https://ep-example.neonauth.c-7.eu-central-1.aws.neon.tech/admin',
                  'https://ep-example.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth#fragment',
                  '', '\n'+BASE]:
            with self.subTest(x=x): self.assertFalse(validate_auth_url(x))
    def test_configuration_off(self):
        c = auth_configuration_status({})
        self.assertFalse(c['neon_auth_url_configured'])
        self.assertFalse(c['mcp_oauth_enabled'])
        self.assertEqual(c['neon_auth_reachability'], 'NOT_TESTED')
    def test_configuration_on_remains_fail_closed(self):
        c = auth_configuration_status({'NEON_AUTH_URL': BASE})
        self.assertTrue(c['neon_auth_url_configured'])
        self.assertTrue(c['neon_auth_url_valid'])
        self.assertFalse(c['neon_session_integration_enabled'])
        self.assertFalse(c['consent_submission_enabled'])
    def test_live_200_probe(self):
        seen=[]
        def handler(r):
            seen.append(r.url.path)
            self.assertNotIn('Authorization', r.headers)
            return httpx.Response(200, json=None)
        ok, status=check_auth_connection({'NEON_AUTH_URL': BASE}, httpx.MockTransport(handler))
        self.assertTrue(ok);self.assertEqual(status,'REACHABLE_UNAUTHENTICATED')
        self.assertEqual(seen,['/neondb/auth/get-session'])
    def test_unauthorized(self):
        ok, code=check_auth_connection({'NEON_AUTH_URL': BASE}, httpx.MockTransport(lambda r: httpx.Response(401)))
        self.assertTrue(ok);self.assertEqual(code,'REACHABLE_REQUIRES_SESSION')
    def test_redirect_not_followed(self):
        ok, code=check_auth_connection({'NEON_AUTH_URL': BASE}, httpx.MockTransport(lambda r: httpx.Response(302, headers={'Location': 'https://evil.org'})))
        self.assertFalse(ok);self.assertEqual(code,'UNEXPECTED_RESPONSE')
    def test_bad_env_skips_network(self):
        ok, code=check_auth_connection({'NEON_AUTH_URL': 'http://localhost/'})
        self.assertFalse(ok);self.assertEqual(code,'INVALID_CONFIGURATION')
    def test_health_version_in_source(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'garminai_public' / 'http_server.py').read_text()
        self.assertIn('\"version\":\"0.8.4.3\"', source)
    def test_status_remains_fail_closed(self):
        from garminai_public.oauth_provider_compat import deployment_requirements
        report = deployment_requirements()
        self.assertFalse(report['mcp_oauth_enabled'])
        self.assertFalse(report['consent_submission_enabled'])

if __name__ == '__main__': unittest.main()
