"""0.9.2 local, offline tests for the *operator-enabled* ChatGPT client.

These tests do NOT establish that ChatGPT/Neon live connection succeeds.
"""
import asyncio
import base64
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from garminai_public.chatgpt_staging import (
    _exact_chatgpt_callback, configuration, status,
)
from garminai_public.oauth_ui_staging import _profile_for_signed_request, configuration as ui_config, consent_page, login_page
from garminai_public.oauth_resource_staging import build_contract, metadata
from garminai_public.mcp_oauth_gateway import StagingOAuthGate
from test_mcp_oauth_gateway_v088 import ENV, ISSUER, RESOURCE, CLIENT, HOST, FakeKeys

CHATGPT_ID = 'chatgpt-staging-public-client-9001'
CHATGPT_CALLBACK = 'https://chatgpt.com/connector_platform_oauth_redirect'
CHATGPT_ENV = {**ENV,
    'GARMINAI_CHATGPT_MCP_STAGING_ENABLED':'1',
    'GARMINAI_CHATGPT_OAUTH_CLIENT_ID':CHATGPT_ID,
    'GARMINAI_CHATGPT_OAUTH_CALLBACK':CHATGPT_CALLBACK,
}


class ChatGPTRegistrationTests(unittest.TestCase):
    def test_disabled_by_default_isolated_from_previous_e2e(self):
        self.assertFalse(configuration(ENV)['enabled'])
        self.assertEqual(configuration(ENV)['issues'], [])
        self.assertTrue(ui_config(ENV)['enabled'])
        with patch.dict('os.environ',ENV,clear=True):
            status_resp = asyncio.run(status(None))
            info=json.loads(status_resp.body)
            self.assertFalse(info['chatgpt_connector_enabled'])
            self.assertFalse(info['real_garmin_access_enabled'])
            self.assertFalse(info['public_plugin_published'])

    def test_explicit_opt_in_with_exact_callback_and_separate_client(self):
        self.assertTrue(configuration(CHATGPT_ENV)['enabled'])
        self.assertTrue(_exact_chatgpt_callback(CHATGPT_CALLBACK))
        self.assertTrue(_exact_chatgpt_callback('https://chatgpt.com/connector/oauth/callback_1234'))
        for bad in ('', 'http://chatgpt.com/connector_platform_oauth_redirect',
                    'https://chatgpt.com.evil.test/connector_platform_oauth_redirect',
                    'https://chatgpt.com/connector_platform_oauth_redirect?state=secret',
                    'https://chatgpt.com/connector_platform_oauth_redirect#frag',
                    'https://chatgpt.com/connector/oauth/short',
                    'https://chatgpt.com:443/connector_platform_oauth_redirect',
                    'https://user:password@chatgpt.com/connector_platform_oauth_redirect',
                    'https://chatgpt.com/oauth/client.json',
                    'https://evil.test/callback'):
            with self.subTest(bad=bad):
                self.assertFalse(_exact_chatgpt_callback(bad))
                self.assertFalse(configuration({**CHATGPT_ENV,'GARMINAI_CHATGPT_OAUTH_CALLBACK':bad})['enabled'])
        for change in (
            {'GARMINAI_CHATGPT_OAUTH_CLIENT_ID': CLIENT},
            {'GARMINAI_CHATGPT_OAUTH_CLIENT_ID': 'https://chatgpt.com/oauth/evil.json'},
            {'GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED': '0'},
            {'GARMINAI_OAUTH_E2E_STAGING_ENABLED': '0'},
            {'RENDER_EXTERNAL_HOSTNAME':'fake.onrender.com'},
        ):
            with self.subTest(change=change):
                c=configuration({**CHATGPT_ENV,**change})
                self.assertFalse(c['enabled'])
                self.assertNotEqual(c['issues'], [])

    def test_official_cimd_identity_is_explicitly_allowlisted(self):
        from garminai_public.chatgpt_staging import _CHATGPT_CIMD_ID
        env={**CHATGPT_ENV, 'GARMINAI_CHATGPT_OAUTH_CLIENT_ID':_CHATGPT_CIMD_ID}
        c=configuration(env)
        self.assertTrue(c['enabled'])
        self.assertEqual(c['client_id'],_CHATGPT_CIMD_ID)
        with patch.dict('os.environ',env,clear=True):
            cfg=ui_config(env)
            req=SimpleNamespace(query_params={'client_id':_CHATGPT_CIMD_ID})
            selected=_profile_for_signed_request(req,cfg)
            self.assertEqual(selected['client_id'],_CHATGPT_CIMD_ID)
            self.assertEqual(selected['callback'],CHATGPT_CALLBACK)
            html=asyncio.run(login_page(req)).body.decode()
            self.assertIn('data-chatgpt-client="true"',html)
            self.assertIn('https://chatgpt.com/oauth/client.json',html)
            st=json.loads(asyncio.run(status(None)).body)
            self.assertEqual(st['version'],'0.9.2')
            self.assertEqual(st['expected_neon_registration'],'CIMD_DISCOVERY_NO_MANUAL_CLIENT')
        for override in (
            {'GARMINAI_CHATGPT_OAUTH_CLIENT_ID':'https://evil.test/client.json'},
            {'GARMINAI_CHATGPT_OAUTH_CLIENT_ID':'https://chatgpt.com/oauth/other.json'},
            {'GARMINAI_CHATGPT_OAUTH_CLIENT_ID':'http://chatgpt.com/oauth/client.json'},
            {'GARMINAI_CHATGPT_OAUTH_CALLBACK':'https://chatgpt.com/connector/oauth/callback1234'},
        ):
            with self.subTest(override=override):
                checked=configuration({**env,**override})
                self.assertFalse(checked['enabled'])
                self.assertTrue(checked['issues'])

    def test_untrusted_query_only_selects_operator_profile(self):
        cfg=ui_config(CHATGPT_ENV)
        req=lambda client: SimpleNamespace(query_params={'client_id':client})
        with patch.dict('os.environ',CHATGPT_ENV,clear=True):
            profile=_profile_for_signed_request(req(CHATGPT_ID),cfg)
            self.assertEqual(profile['callback'],CHATGPT_CALLBACK)
            self.assertEqual(profile['client_id'],CHATGPT_ID)
            other=_profile_for_signed_request(req('attacker-client-id'),cfg)
            self.assertEqual(other['client_id'],CLIENT)
            # The query is never interpolated in rendered HTML.
            page=asyncio.run(consent_page(req(CHATGPT_ID))).body.decode()
            self.assertIn('data-chatgpt-client="true"',page)
            self.assertIn('data-client-id="'+CHATGPT_ID+'"',page)
            self.assertIn('data-callback="'+CHATGPT_CALLBACK+'"',page)
            self.assertNotIn('attacker-client-id',page)
            legacy=asyncio.run(login_page(req(CLIENT))).body.decode()
            self.assertIn('data-chatgpt-client="false"',legacy)
            self.assertIn('data-callback="https://'+HOST+'/auth/oauth-test/callback"',legacy)

    def test_discovery_is_path_bound_and_does_not_expose_private_data(self):
        with patch.dict('os.environ',CHATGPT_ENV,clear=True):
            contract=build_contract()
            self.assertEqual(contract.resource,RESOURCE)
            self.assertIn('oauth-protected-resource/mcp-oauth-staging',contract.challenge())
            page=asyncio.run(metadata(None))
            self.assertEqual(page.status_code,200)
            doc=json.loads(page.body)
            self.assertEqual(doc['resource'],RESOURCE)
            self.assertEqual(doc['authorization_servers'],[ISSUER])
            self.assertNotIn('client_id',doc)
            self.assertNotIn('access_token',doc)


class ChatGPTGateTests(unittest.TestCase):
    def test_only_two_allowlisted_verified_client_ids(self):
        signer=ed25519.Ed25519PrivateKey.generate()
        pub=signer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        jwk={'kty':'OKP','crv':'Ed25519',
             'x':base64.urlsafe_b64encode(pub).rstrip(b'=').decode(),
             'kid':'testing-key','use':'sig','alg':'EdDSA'}
        keys=FakeKeys({'keys':[jwk]})
        now=int(time.time())
        def signed(client,*,aud=RESOURCE,scope='openid',exp=None):
            return jwt.encode({'iss':ISSUER,'sub':'test-subject','aud':aud,'azp':client,
                 'scope':scope,'iat':now-4,'exp':now+120 if exp is None else exp},
                 signer,algorithm='EdDSA',headers={'kid':'testing-key','typ':'at+jwt'})
        passed=[]
        async def inner(scope,receive,send):
            passed.append(scope)
            await send({'type':'http.response.start','status':200,'headers':[]})
            await send({'type':'http.response.body','body':b'{}'})
        gateway=StagingOAuthGate(inner,jwks=keys)
        async def request(env,token):
            events=[]
            async def send(msg):events.append(msg)
            async def receive():return {'type':'http.request','body':b'', 'more_body':False}
            scope={'type':'http','path':'/mcp-oauth-staging','raw_path':b'/mcp-oauth-staging',
                   'method':'POST','headers':[(b'authorization',b'Bearer '+token.encode())]}
            with patch.dict('os.environ',env,clear=True):
                await gateway(scope,receive,send)
            return next(e['status'] for e in events if e['type']=='http.response.start'),events
        async def scenario():
            self.assertEqual((await request(CHATGPT_ENV,signed(CHATGPT_ID)))[0],200)
            self.assertEqual((await request(CHATGPT_ENV,signed(CLIENT)))[0],200)
            cimd_env={**CHATGPT_ENV,'GARMINAI_CHATGPT_OAUTH_CLIENT_ID':'https://chatgpt.com/oauth/client.json'}
            self.assertEqual((await request(cimd_env,signed('https://chatgpt.com/oauth/client.json',scope='openid email offline_access')))[0],200)
            self.assertEqual((await request(cimd_env,signed('https://chatgpt.com/oauth/evil.json')))[0],401)
            for token in (signed('unknown-client'),signed(CHATGPT_ID,aud='https://evil.test/mcp'),
                          signed(CHATGPT_ID,scope='profile'),signed(CHATGPT_ID,exp=now-200)):
                code,events=await request(CHATGPT_ENV,token)
                self.assertEqual(code,401)
                hdr=dict(next(e['headers'] for e in events if e['type']=='http.response.start'))
                self.assertIn(b'resource_metadata=',hdr[b'www-authenticate'])
            self.assertEqual((await request(ENV,signed(CHATGPT_ID)))[0],401)
            self.assertEqual((await request(ENV,signed(CLIENT)))[0],200)
            self.assertEqual(len(passed),4)
            self.assertTrue(all('garminai.oauth_staging_principal' in scope for scope in passed))
            self.assertTrue(all(not any(k.lower()==b'authorization' for k,v in scope['headers']) for scope in passed))
        asyncio.run(scenario())

if __name__ == '__main__': unittest.main()
