"""v0.9.2: offline security and stability tests, NO external accounts/network.

Two-user tests emulate independently issued SIGNED JWTs. They do not prove
that a second live ChatGPT account has been tested.
"""
import asyncio
import base64
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from starlette.applications import Starlette
from starlette.routing import Route

from garminai_public.demo_tenant import DemoPrincipal, activities_for, detail_for
from garminai_public.mcp_oauth_gateway import StagingOAuthGate
from test_mcp_oauth_gateway_v088 import ENV, ISSUER, RESOURCE, HOST, CLIENT, FakeKeys

CIMD = 'https://chatgpt.com/oauth/client.json'
STAGING = {**ENV, 'GARMINAI_CHATGPT_MCP_STAGING_ENABLED':'1',
           'GARMINAI_CHATGPT_OAUTH_CLIENT_ID':CIMD,
           'GARMINAI_CHATGPT_OAUTH_CALLBACK':'https://chatgpt.com/connector_platform_oauth_redirect'}


class JWTFixture:
    def __init__(self):
        self.key = ed25519.Ed25519PrivateKey.generate()
        pub = self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.keys = FakeKeys({'keys':[{'kty':'OKP','crv':'Ed25519','kid':'key092',
            'x':base64.urlsafe_b64encode(pub).rstrip(b'=').decode(),
            'use':'sig','alg':'EdDSA'}]})

    def token(self, subject='A', *, client=CIMD, expiry_delta=120, aud=RESOURCE,
              scopes='openid email offline_access', nonce='one'):
        now = int(time.time())
        return jwt.encode({'iss':ISSUER,'sub':subject,'aud':aud,'azp':client,
            'scope':scopes,'iat':now-1,'exp':now+expiry_delta,'jti':nonce},
            self.key, algorithm='EdDSA', headers={'kid':'key092','typ':'at+jwt'})


class StabilizedMCP(unittest.TestCase):
    def setUp(self):
        self.fixture = JWTFixture()
        self.seen = []

        async def inner(scope, receive, send):
            self.seen.append(scope)
            assert scope['path']=='/mcp'
            assert all(k.lower()!=b'authorization' for k,_ in scope['headers'])
            principal = scope['garminai.oauth_staging_principal']
            assert isinstance(principal,DemoPrincipal)
            body = b''
            while True:
                msg=await receive()
                body+=msg.get('body',b'')
                if not msg.get('more_body'):
                    break
            parsed=json.loads(body) if body else {'op':'status'}
            if parsed.get('op')=='list':
                payload=activities_for(principal,2)
            elif parsed.get('op')=='detail':
                payload=detail_for(principal,parsed['activity_id'])
            else:
                payload={'mode':'DEMO_ONLY'}
            data=json.dumps(payload).encode()
            await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'application/json')]})
            await send({'type':'http.response.body','body':data})

        self.app=Starlette(routes=[Route('/mcp-oauth-staging',
            StagingOAuthGate(inner,jwks=self.fixture.keys),methods=['POST'])])

    async def post(self, token=None, *, headers=None, data=None):
        all_headers={}
        if token is not None:
            all_headers['Authorization']='Bearer '+token
        if headers:
            all_headers.update(headers)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                  base_url='https://'+HOST) as client:
            return await client.post('/mcp-oauth-staging',headers=all_headers,
                  json=data if data is not None else {'op':'status'})

    def scenario(self, coro):
        with patch.dict('os.environ',STAGING,clear=True):
            return asyncio.run(coro)

    def test_expired_token_rejected_even_during_jwt_leeway_window(self):
        async def run():
            for age in (-1,-10,-29):
                res=await self.post(self.fixture.token(expiry_delta=age))
                self.assertEqual(res.status_code,401)
                self.assertEqual(res.json(),{'error':'invalid_token'})
                self.assertEqual(res.headers['cache-control'],'no-store')
                self.assertEqual(res.headers['x-content-type-options'],'nosniff')
                self.assertEqual(res.headers['referrer-policy'],'no-referrer')
                self.assertIn('resource_metadata=',res.headers['www-authenticate'])
                self.assertIn('error="invalid_token"',res.headers['www-authenticate'])
            self.assertFalse(self.seen)
        self.scenario(run())

    def test_refreshed_access_token_same_verified_subject_same_view(self):
        async def run():
            t1=self.fixture.token(subject='athlete-A',nonce='first')
            t2=self.fixture.token(subject='athlete-A',nonce='refreshed')
            a=await self.post(t1,data={'op':'list'})
            b=await self.post(t2,data={'op':'list'})
            self.assertEqual(a.status_code,b.status_code)
            self.assertEqual(a.status_code,200)
            self.assertEqual(a.json(),b.json())
            self.assertNotIn('athlete-A',a.text)
            self.assertNotIn(t1,a.text)
            self.assertNotIn(t2,b.text)
        self.scenario(run())

    def test_simulated_two_accounts_concurrent_and_foreign_denials(self):
        async def run():
            a=self.fixture.token(subject='Neon-A',nonce='A')
            b=self.fixture.token(subject='Neon-B',nonce='B')
            result=await asyncio.gather(self.post(a,data={'op':'list'}),self.post(b,data={'op':'list'}))
            self.assertTrue(all(x.status_code==200 for x in result))
            ids=[x.json()['activities'][0]['id'] for x in result]
            self.assertNotEqual(*ids)
            same_a,denied_a,denied_b,same_b=await asyncio.gather(
                self.post(a,data={'op':'detail','activity_id':ids[0]}),
                self.post(a,data={'op':'detail','activity_id':ids[1]}),
                self.post(b,data={'op':'detail','activity_id':ids[0]}),
                self.post(b,data={'op':'detail','activity_id':ids[1]}))
            self.assertEqual(same_a.json()['activity']['id'],ids[0])
            self.assertEqual(same_b.json()['activity']['id'],ids[1])
            self.assertEqual(denied_a.json(),{'mode':'DEMO_ONLY','error':'unknown_demo_activity'})
            self.assertEqual(denied_b.json(),{'mode':'DEMO_ONLY','error':'unknown_demo_activity'})
            self.assertEqual(len(self.seen),6)
            for response in result:
                self.assertNotIn('Neon-A',response.text)
                self.assertNotIn('Neon-B',response.text)
        self.scenario(run())

    def test_wrong_client_audience_scope_and_legacy_client_without_optin(self):
        async def run():
            for token in (self.fixture.token(client='https://attacker.test/client.json'),
                          self.fixture.token(aud='https://attacker.test/mcp'),
                          self.fixture.token(scopes='email offline_access')):
                r=await self.post(token)
                self.assertEqual(r.status_code,401)
            self.assertFalse(self.seen)
        self.scenario(run())
        with patch.dict('os.environ',ENV,clear=True):
            r=asyncio.run(self.post(self.fixture.token()))
        self.assertEqual(r.status_code,401)

    def test_missing_token_triggers_discovery_without_data_leak(self):
        async def run():
            r=await self.post()
            self.assertEqual(r.status_code,401)
            self.assertEqual(r.json(),{'error':'invalid_token'})
            self.assertIn('resource_metadata=',r.headers['www-authenticate'])
            self.assertEqual(r.headers['cache-control'],'no-store')
            self.assertEqual(self.fixture.keys.called,[])
        self.scenario(run())

    def test_declared_oversize_and_bad_lengths_rejected_pre_jwks(self):
        async def run():
            # Content-Length is set by HTTPX, so simulate a larger body to
            # exercise the declared-body guard without reaching the MCP app.
            r=await self.post(self.fixture.token(),data={'x':'X'*(65536+1)})
            self.assertEqual(r.status_code,413)
            self.assertEqual(r.json(),{'error':'request_too_large'})
            self.assertEqual(self.fixture.keys.called,[])
            self.assertEqual(self.seen,[])
        self.scenario(run())

    def test_keys_outage_returns_retry_after_without_subject_or_token(self):
        self.fixture.keys.error=True
        token=self.fixture.token(subject='sensitive-subject')
        async def run():
            r=await self.post(token)
            self.assertEqual(r.status_code,503)
            self.assertEqual(r.headers['retry-after'],'5')
            self.assertEqual(r.json(),{'error':'signing_keys_unavailable'})
            self.assertNotIn('sensitive-subject',r.text)
            self.assertNotIn(token,r.text)
            self.assertFalse(self.seen)
        self.scenario(run())

    def test_tool_descriptions_are_clear_and_readonly(self):
        import ast
        p=Path(__file__).resolve().parents[1]/'garminai_public/mcp_oauth_demo.py'
        root=ast.parse(p.read_text(encoding='utf-8'))
        tools={node.name:ast.get_docstring(node) for node in root.body
               if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and any(
                 isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute)
                 and dec.func.attr=='tool' for dec in node.decorator_list)}
        self.assertEqual(set(tools),{'get_sync_status','get_activities','get_demo_activity_details','get_garmin_connection_link','get_garmin_connection_status','disconnect_garmin_account','run_synthetic_push_rehearsal'})
        for name in ('get_sync_status','get_activities','get_demo_activity_details'):
            description=tools[name]
            self.assertIn('read-only',description.lower(),name)
            self.assertIn('fictional',description.lower(),name)
        for name in ('get_garmin_connection_link','get_garmin_connection_status','disconnect_garmin_account'):
            self.assertIn('Garmin',tools[name],name)

if __name__=='__main__': unittest.main()
