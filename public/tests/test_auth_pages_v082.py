import asyncio
import unittest
from types import SimpleNamespace
from garminai_public.auth_pages import login_page, consent_page
from garminai_public.oauth_provider_compat import deployment_requirements


class AuthPagesTests(unittest.TestCase):
    def response(self, fn, query=''):
        return asyncio.run(fn(SimpleNamespace(url=SimpleNamespace(query=query))))

    def test_login_is_disabled_and_nostore(self):
        r = self.response(login_page)
        s = r.body.decode()
        self.assertEqual(r.status_code, 200)
        self.assertIn('Sign-in is not active yet', s)
        self.assertIn('aria-disabled="true"', s)
        self.assertIn('no-store', r.headers['cache-control'])
        self.assertIn("form-action 'none'", r.headers['content-security-policy'])

    def test_consent_is_not_interactive(self):
        r = self.response(consent_page)
        self.assertIn('No client permissions are granted', r.body.decode())
        self.assertIn('Approve — unavailable', r.body.decode())
        self.assertNotIn('<form', r.body.decode().lower())
        self.assertEqual(r.headers['referrer-policy'], 'no-referrer')

    def test_query_not_rendered(self):
        # OAuth query must not be echoed into HTML/JS before verified by Neon.
        payload = 'SECRET_OAUTH_QUERY_DO_NOT_ECHO'
        for fn in (login_page, consent_page):
            self.assertNotIn(payload, self.response(fn, payload).body.decode())

    def test_readiness_fail_closed(self):
        state = deployment_requirements()
        self.assertEqual(state['version'], '0.8.4')
        self.assertTrue(state['staging_login_page_available'])
        self.assertFalse(state['consent_submission_enabled'])
        self.assertFalse(state['mcp_oauth_enabled'])

    def test_server_routes_are_present(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'garminai_public' / 'http_server.py').read_text()
        self.assertIn('Route("/auth/login", login_page)', source)
        self.assertIn('Route("/auth/consent", consent_page)', source)

if __name__ == '__main__':
    unittest.main()
