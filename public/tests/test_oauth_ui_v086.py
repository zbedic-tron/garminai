"""Independent staging-only OAuth UI tests; no calls to Neon or Google."""
import asyncio
from pathlib import Path
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from garminai_public.oauth_ui_staging import (
    configuration, login_page, consent_page, ui_js, ui_status, _JS
)

BASE='https://ep-test.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth'
HOST='garminai-public-demo.onrender.com'
CLIENT='garminai-test-public-client-001'
CALLBACK='https://'+HOST+'/auth/oauth-test/callback'
ENV={'RENDER_EXTERNAL_HOSTNAME':HOST,'NEON_AUTH_STAGING_URL':BASE, 'GARMINAI_OAUTH_TEST_CLIENT_ID':CLIENT}


def call(fn):
    return asyncio.run(fn(SimpleNamespace()))


class OAuthUiTests(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertFalse(configuration(ENV)['enabled'])
        with patch.dict('os.environ',ENV,clear=True):
            self.assertIn('Sign-in is not active yet',call(login_page).body.decode())
            self.assertIn('Consent is not active yet',call(consent_page).body.decode())
            self.assertEqual(call(ui_js).status_code,404)
            self.assertFalse(json.loads(call(ui_status).body)['oauth_ui_staging_enabled'])

    def test_staging_flag_and_host_validation(self):
        c=configuration({**ENV,'GARMINAI_OAUTH_UI_STAGING_ENABLED':'1'})
        self.assertTrue(c['enabled'])
        self.assertEqual(c['resource'],'https://'+HOST+'/mcp-oauth-staging')
        for change in ({'RENDER_EXTERNAL_HOSTNAME':'garminai.example.com'},
                       {'RENDER_EXTERNAL_HOSTNAME':'fake.onrender.com.evil.test'},
                       {'RENDER_EXTERNAL_HOSTNAME':'../evil.onrender.com'},
                       {'NEON_AUTH_STAGING_URL':'https://evil.test/auth'},
                       {'NEON_AUTH_STAGING_URL':'http://'+BASE[8:]},
                       {'NEON_AUTH_STAGING_URL':BASE+'?password=foo'},
                       {'GARMINAI_OAUTH_TEST_CLIENT_ID':''},
                       {'GARMINAI_OAUTH_TEST_CLIENT_ID':'https://evil.test/client'}):
            with self.subTest(change=change):
                e={**ENV,'GARMINAI_OAUTH_UI_STAGING_ENABLED':'1',**change}
                self.assertFalse(configuration(e)['enabled'])
                self.assertNotEqual(configuration(e)['issues'],[])

    def test_active_pages_no_query_reflection_csp_and_explicit_consent(self):
        env={**ENV,'GARMINAI_OAUTH_UI_STAGING_ENABLED':'1'}
        with patch.dict('os.environ',env,clear=True):
            for f in (login_page, consent_page):
                r=call(f)
                self.assertEqual(r.status_code,200)
                self.assertIn('no-store',r.headers['cache-control'])
                self.assertEqual(r.headers['referrer-policy'],'no-referrer')
                self.assertIn("frame-ancestors 'none'",r.headers['content-security-policy'])
                self.assertIn("script-src 'self'",r.headers['content-security-policy'])
                self.assertIn(BASE.split('/neondb')[0],r.headers['content-security-policy'])
                self.assertIn('data-auth=',r.body.decode())
                self.assertNotIn('oauth_query=',r.body.decode())
                self.assertNotIn('SECRET_TOKEN',r.body.decode())
            consent=call(consent_page).body.decode()
            self.assertIn('id="allow" disabled',consent)
            self.assertIn('id="deny" class="deny" disabled',consent)
            self.assertIn('id="client" hidden',consent)
            self.assertIn('id="rights" hidden',consent)
            js=call(ui_js)
            self.assertEqual(js.status_code,200)
            self.assertIn('javascript',js.media_type)
            self.assertIn('no-store',js.headers['cache-control'])
            status=json.loads(call(ui_status).body)
            self.assertTrue(status['oauth_ui_staging_enabled'])
            self.assertFalse(status['provider_enabled_by_this_app'])
            self.assertFalse(status['mcp_authenticated_tools_enabled'])
            self.assertFalse(status['garmin_live_data_enabled'])

    def test_javascript_never_does_unverified_grants_or_user_token_storage(self):
        self.assertNotIn("/oauth2/public-client-prelogin",_JS)
        self.assertIn("/oauth2/public-client?client_id=",_JS)
        self.assertIn("/oauth2/continue",_JS)
        self.assertNotIn("const url = new URL(base + '/oauth2/authorize')", _JS)
        self.assertIn("selected:true, oauth_query:signed.toString()", _JS)
        self.assertIn("expectedClient",_JS)
        self.assertIn("expectedCallback",_JS)
        self.assertIn('oauth_query:signed.toString()',_JS)
        self.assertIn("/oauth2/consent",_JS)
        self.assertIn('data-mode',call_src())
        self.assertNotIn('localStorage',_JS)
        self.assertNotIn('eval(',_JS)
        self.assertNotIn('innerHTML',_JS)
        self.assertNotIn('Authorization: Bearer',_JS)
        self.assertIn('maxAgeMs = 10 * 60 * 1000',_JS)
        self.assertEqual((Path(__file__).parent / 'js' / 'oauth_ui_v086.js').read_text(), _JS)

    def test_health_and_existing_demo_gate_unchanged(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/'garminai_public'/'http_server.py').read_text()
        self.assertIn('DemoBearerGate(mcp_asgi)',source)
        self.assertIn('Route("/auth/oauth-ui/status", ui_status)',source)
        self.assertIn('Route("/auth/oauth-ui.js", ui_js)',source)
        self.assertIn('"version":"0.9.0"',source)


def call_src():
    from garminai_public.oauth_ui_staging import _response
    return _response(mode='consent',base=BASE,resource='https://'+HOST+'/mcp-oauth-staging',client_id=CLIENT,callback=CALLBACK).body.decode()


if __name__=='__main__': unittest.main()
