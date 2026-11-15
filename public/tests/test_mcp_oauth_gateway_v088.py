"""v0.8.8 offline auth-gate tests: mock Neon keys, never real credentials/network."""
import asyncio
import base64
import json
import time
import unittest
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from garminai_public.mcp_oauth_gateway import StagingOAuthGate, configured, _FixedIssuerJWKS

ISSUER = 'https://ep-test.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth'
HOST = 'garminai-public-demo.onrender.com'
RESOURCE = 'https://' + HOST + '/mcp-oauth-staging'
CLIENT = 'garminai-test-public-client-001'
ENV = {'RENDER_EXTERNAL_HOSTNAME':HOST, 'NEON_AUTH_STAGING_URL':ISSUER,
       'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'1',
       'GARMINAI_MCP_OAUTH_STAGING_ISSUER':ISSUER,
       'GARMINAI_OAUTH_UI_STAGING_ENABLED':'1',
       'GARMINAI_OAUTH_E2E_STAGING_ENABLED':'1',
       'GARMINAI_OAUTH_TEST_CLIENT_ID':CLIENT,
       'GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED':'1'}


def make_token(*, aud=RESOURCE, client=CLIENT, scope='openid', exp=None):
    private = ed25519.Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    jwk={'kty':'OKP','crv':'Ed25519','x':base64.urlsafe_b64encode(raw).rstrip(b'=').decode(),
         'kid':'testkey','use':'sig','alg':'EdDSA'}
    now=int(time.time())
    token = jwt.encode({'iss':ISSUER,'sub':'test-id','aud':aud,'azp':client,
                        'scope':scope,'iat':now-10,'exp':now+90 if exp is None else exp},
                       private,algorithm='EdDSA',headers={'kid':'testkey','typ':'at+jwt'})
    return token, {'keys':[jwk]}


class FakeKeys:
    def __init__(self, jwks=None, error=False):
        self.jwks=jwks
        self.error=error
        self.called=[]
    async def get(self, issuer):
        self.called.append(issuer)
        if self.error: raise RuntimeError('JWKS_UNAVAILABLE')
        return self.jwks


class TestGateway(unittest.TestCase):
    @staticmethod
    def run_request(*, env=ENV, auth=None, app=None, keys=None, method='POST', path='/mcp-oauth-staging', dup=False):
        seen=[]
        async def downstream(scope, receive, send):
            seen.append(scope)
            await send({'type':'http.response.start','status':200,
                        'headers':[(b'content-type',b'application/json')]})
            await send({'type':'http.response.body','body':b'{"ok":true}'})
        headers=[(b'host',HOST.encode())]
        if auth:
            headers.append((b'authorization',auth.encode()))
            if dup: headers.append((b'Authorization',auth.encode()))
        scope={'type':'http','method':method,'path':path,'raw_path':path.encode(),
               'root_path':'','headers':headers,'scheme':'https','server':(HOST,443)}
        messages=[]
        async def send(message): messages.append(message)
        async def receive(): return {'type':'http.request','body':b'', 'more_body':False}
        async def run():
            with patch.dict('os.environ',env,clear=True):
                await StagingOAuthGate(app or downstream,jwks=keys)(scope,receive,send)
        asyncio.run(run())
        status = next(m['status'] for m in messages if m['type']=='http.response.start')
        body = b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body')
        return status, body, seen, messages

    def test_explicit_separate_opt_in(self):
        self.assertTrue(configured(ENV)['enabled'])
        self.assertFalse(configured({**ENV, 'GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED':'0'})['enabled'])
        self.assertFalse(configured({**ENV, 'GARMINAI_OAUTH_E2E_STAGING_ENABLED':'0'})['enabled'])
        self.assertFalse(configured({**ENV, 'RENDER_EXTERNAL_HOSTNAME':'attacker.com'})['enabled'])

    def test_gate_unchanged_challenge_when_disabled(self):
        status, body, seen, messages=self.run_request(env={**ENV,'GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED':'0'})
        self.assertEqual(status,401)
        self.assertEqual(seen,[])
        self.assertIn(b'oauth_required',body)
        self.assertTrue(any(k==b'www-authenticate' for k,v in messages[0]['headers']))
        status, _, seen, _=self.run_request(env={**ENV,'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'0'})
        self.assertEqual(status,404)
        self.assertFalse(seen)

    def test_rejects_missing_malformed_and_duplicate(self):
        for token, dup in ((None,False),('Basic 123',False),('Bearer bad',False),('Bearer '+('A'*100),False),('Bearer '+('A'*100),True)):
            with self.subTest(token=token,dup=dup):
                k=FakeKeys({'keys':[]})
                status,_,seen,_=self.run_request(auth=token, dup=dup, keys=k)
                self.assertEqual(status,401)
                self.assertFalse(seen)
                self.assertEqual(k.called,[])

    def test_valid_jwt_reaches_only_isolated_mcp_without_authorization_header(self):
        token, jwks=make_token()
        k=FakeKeys(jwks)
        status,body,seen,_=self.run_request(auth='Bearer '+token,keys=k)
        self.assertEqual(status,200)
        self.assertEqual(body,b'{"ok":true}')
        self.assertEqual(len(seen),1)
        self.assertEqual(seen[0]['path'],'/mcp')
        self.assertFalse(any(key.lower()==b'authorization' for key,_ in seen[0]['headers']))
        self.assertEqual(k.called,[ISSUER])

    def test_fail_closed_jwt_substitution_and_expiry(self):
        cases = ({'aud':'https://evil.example.com'}, {'client':'different-client'},
                 {'scope':'profile'}, {'exp':int(time.time())-100})
        for change in cases:
            with self.subTest(change=change):
                token,jwks=make_token(**change)
                status,_,seen,_=self.run_request(auth='Bearer '+token,keys=FakeKeys(jwks))
                self.assertEqual(status,401)
                self.assertFalse(seen)

    def test_jwks_outage_never_opens_gate(self):
        token,jwks=make_token()
        status,body,seen,_=self.run_request(auth='Bearer '+token,keys=FakeKeys(error=True))
        self.assertEqual(status,503)
        self.assertIn(b'signing_keys_unavailable',body)
        self.assertFalse(seen)

    def test_only_exact_mcp_path(self):
        token,jwks=make_token()
        status,_,seen,_=self.run_request(auth='Bearer '+token,keys=FakeKeys(jwks), path='/evil')
        self.assertEqual(status,404)
        self.assertFalse(seen)

    def test_short_cache_and_failure_fails_closed(self):
        import httpx
        data={'keys':[{'kid':'one'}]}
        calls=[]
        def respond(request):
            calls.append(str(request.url))
            return httpx.Response(200,json=data)
        real=httpx.AsyncClient
        def factory(*args,**kwargs):
            return real(*args,transport=httpx.MockTransport(respond),**kwargs)
        cache=_FixedIssuerJWKS()
        with patch('garminai_public.mcp_oauth_gateway.httpx.AsyncClient',side_effect=factory):
            first=asyncio.run(cache.get(ISSUER))
            second=asyncio.run(cache.get(ISSUER))
        self.assertEqual(first,second)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0],ISSUER+'/.well-known/jwks.json')


if __name__=='__main__': unittest.main()

class TestRoutedGatewayAndProbe(unittest.TestCase):
    def test_starlette_route_accepts_asgi_gateway_and_rewrites_exact_path(self):
        import httpx
        from starlette.applications import Starlette
        from starlette.routing import Route
        token,jwks=make_token()
        seen=[]
        async def fake_mcp(scope, receive, send):
            seen.append(scope)
            await send({'type':'http.response.start','status':200,
                        'headers':[(b'content-type',b'application/json')]})
            await send({'type':'http.response.body','body':b'{"jsonrpc":"2.0","id":1,"result":{"ok":true}}'})
        app=Starlette(routes=[Route('/mcp-oauth-staging', StagingOAuthGate(fake_mcp,jwks=FakeKeys(jwks)), methods=['POST'])])
        async def request():
            transport=httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport,base_url='https://'+HOST) as client:
                return await client.post('/mcp-oauth-staging',headers={'Authorization':'Bearer '+token},json={})
        with patch.dict('os.environ',ENV,clear=True):
            response=asyncio.run(request())
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['result']['ok'],True)
        self.assertEqual(seen[0]['path'],'/mcp')

    def test_internal_mcp_probe_accepts_only_fictional_tool_list_and_call(self):
        import sys
        import types
        from starlette.applications import Starlette
        from starlette.routing import Route
        from garminai_public.oauth_e2e_staging import _probe_demo_mcp
        token,jwks=make_token()
        seen=[]
        async def fake_mcp(scope, receive, send):
            b=b''
            while True:
                m=await receive()
                b+=m.get('body',b'')
                if not m.get('more_body'): break
            rpc=json.loads(b)
            seen.append((scope['path'],rpc.get('method')))
            method=rpc.get('method')
            if method=='initialize': result={'protocolVersion':'2025-03-26','capabilities':{},'serverInfo':{}}
            elif method=='tools/list': result={'tools':[{'name':'get_sync_status'}, {'name':'get_activities'}, {'name':'get_demo_activity_details'}]}
            elif method=='tools/call':
                rpc_args=rpc.get('params',{})
                name=rpc_args.get('name')
                if name=='get_sync_status': content={'mode':'DEMO_ONLY','garmin_oauth':'NOT_CONNECTED'}
                elif name=='get_activities': content={'mode':'DEMO_ONLY','isolation':'TOKEN_SUBJECT_SCOPED','activities':[{'id':'demo-own-1'},{'id':'demo-own-2'}]}
                elif name=='get_demo_activity_details':
                    rid=rpc_args.get('arguments',{}).get('activity_id')
                    if rid=='demo-own-1': content={'mode':'DEMO_ONLY','activity':{'id':'demo-own-1'}}
                    else: content={'mode':'DEMO_ONLY','error':'unknown_demo_activity'}
                else: content={'mode':'INVALID'}
                result={'content':[{'type':'text','text':json.dumps(content)}]}
            else: result={'error':'unknown'}
            payload=json.dumps({'jsonrpc':'2.0','id':rpc.get('id'),'result':result}).encode()
            await send({'type':'http.response.start','status':200,
                        'headers':[(b'content-type',b'application/json')]})
            await send({'type':'http.response.body','body':payload})
        routed=Starlette(routes=[Route('/mcp-oauth-staging', StagingOAuthGate(fake_mcp,jwks=FakeKeys(jwks)),methods=['POST'])])
        module=types.ModuleType('garminai_public.http_server')
        module.app=routed
        with patch.dict(sys.modules, {'garminai_public.http_server':module}):
            with patch.dict('os.environ',ENV,clear=True):
                result=asyncio.run(_probe_demo_mcp(token,{'origin':'https://'+HOST}))
        self.assertTrue(all(result.values()),result)
        self.assertEqual([x[1] for x in seen], ['initialize','tools/list']+['tools/call']*4)
