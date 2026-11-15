"""Offline v0.8.7 staging tests. No network, Neon users or Garmin data."""
import asyncio
import base64
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.primitives import serialization
from jwt.utils import base64url_encode
from starlette.requests import Request

from garminai_public.oauth_e2e_staging import (
    _check_jwt, _exchange_and_verify, configuration, start, callback, status, script,
    exchange, UnsafeOAuthResponse, _JS,
)

ISSUER='https://ep-test.neonauth.c-7.eu-central-1.aws.neon.tech/neondb/auth'
HOST='garminai-public-demo.onrender.com'
RESOURCE='https://'+HOST+'/mcp-oauth-staging'
CLIENT='garminai-test-public-client-001'
ENV={'RENDER_EXTERNAL_HOSTNAME':HOST, 'NEON_AUTH_STAGING_URL':ISSUER,
     'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'1',
     'GARMINAI_MCP_OAUTH_STAGING_ISSUER':ISSUER,
     'GARMINAI_OAUTH_E2E_STAGING_ENABLED':'1',
     'GARMINAI_OAUTH_TEST_CLIENT_ID':CLIENT}


def run(fn): return asyncio.run(fn(SimpleNamespace()))


def jwt_fixture(*, alg='EdDSA', typ='at+jwt', issuer=ISSUER, aud=RESOURCE, scope='openid', client=CLIENT, exp=None):
    claims={'iss':issuer,'aud':[aud,ISSUER+'/oauth2/userinfo'],'sub':'test-user','iat':int(time.time())-2,
            'exp':exp if exp is not None else int(time.time())+120, 'azp':client, 'scope':scope}
    if alg=='EdDSA':
        private=ed25519.Ed25519PrivateKey.generate()
        pub=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        jwk={'kty':'OKP','crv':'Ed25519','x':base64url_encode(pub).decode(),'kid':'k1','use':'sig','alg':'EdDSA'}
    else:
        private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        public=private.public_key().public_numbers()
        encode=lambda n:base64url_encode(n.to_bytes((n.bit_length()+7)//8,'big')).decode()
        jwk={'kty':'RSA','n':encode(public.n),'e':encode(public.e),'kid':'k1','use':'sig','alg':'RS256'}
    token=jwt.encode(claims,private,algorithm=alg,headers={'kid':'k1','typ':typ})
    return token,{'keys':[jwk]}


class OAuthE2ETests(unittest.TestCase):
    def test_configuration_fail_closed_and_fixed_host(self):
        self.assertTrue(configuration(ENV)['enabled'])
        self.assertEqual(configuration(ENV)['callback'], 'https://'+HOST+'/auth/oauth-test/callback')
        self.assertFalse(configuration({})['enabled'])
        for change in ({'GARMINAI_OAUTH_TEST_CLIENT_ID':''},
                       {'GARMINAI_OAUTH_TEST_CLIENT_ID':'abc'},
                       {'NEON_AUTH_STAGING_URL':'https://evil.test'},
                       {'GARMINAI_MCP_OAUTH_STAGING_ISSUER':'https://evil.test'},
                       {'RENDER_EXTERNAL_HOSTNAME':'evil.onrender.com'},
                       {'GARMINAI_MCP_OAUTH_STAGING_ENABLED':'0'}):
            with self.subTest(change=change):
                self.assertFalse(configuration({**ENV,**change})['enabled'])

    def test_disabled_routes_and_live_page_security_headers(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertEqual(run(start).status_code,404)
            self.assertEqual(run(callback).status_code,404)
            self.assertEqual(run(script).status_code,404)
            self.assertFalse(json.loads(run(status).body)['oauth_e2e_test_enabled'])
        with patch.dict('os.environ',ENV,clear=True):
            for handler in (start,callback):
                r=run(handler)
                self.assertEqual(r.status_code,200)
                self.assertIn("frame-ancestors 'none'",r.headers['content-security-policy'])
                self.assertIn("script-src 'self'",r.headers['content-security-policy'])
                self.assertIn('no-store',r.headers['cache-control'])
                self.assertNotIn('SECRET',r.body.decode())
            self.assertIn('id="start"',run(start).body.decode())
            self.assertNotIn('id="start"',run(callback).body.decode())
            self.assertEqual(run(script).status_code,200)
            self.assertTrue(json.loads(run(status).body)['oauth_e2e_test_enabled'])
            self.assertFalse(json.loads(run(status).body)['garmin_live_data_enabled'])

    def test_token_verifier_accepts_supported_neon_algorithms(self):
        for algorithm in ('RS256','EdDSA'):
            with self.subTest(alg=algorithm):
                token,jwks=jwt_fixture(alg=algorithm)
                self.assertTrue(_check_jwt(token,jwks,issuer=ISSUER,resource=RESOURCE,client_id=CLIENT))

    def test_token_verifier_rejects_substitution_expiry_wrong_issuer_and_scopes(self):
        cases=[{'typ':'JWT'},{'issuer':ISSUER+'/other'},{'aud':'https://evil.test/api'},
               {'scope':'email'},{'client':'other-client-123'}, {'exp':int(time.time())-120}]
        for case in cases:
            with self.subTest(case=case):
                token,jwks=jwt_fixture(**case)
                with self.assertRaises(UnsafeOAuthResponse):
                    _check_jwt(token,jwks,issuer=ISSUER,resource=RESOURCE,client_id=CLIENT)
        token,jwks=jwt_fixture()
        jwks['keys'].append(jwks['keys'][0].copy())
        with self.assertRaises(UnsafeOAuthResponse):
            _check_jwt(token,jwks,issuer=ISSUER,resource=RESOURCE,client_id=CLIENT)
        for bad in ('not-a-token','abc.def.xyz'):
            with self.assertRaises(UnsafeOAuthResponse):
                _check_jwt(bad,{'keys':[]},issuer=ISSUER,resource=RESOURCE,client_id=CLIENT)

    def test_exchange_uses_fixed_endpoints_and_no_token_returned(self):
        import httpx
        token,jwks=jwt_fixture()
        called=[]
        def handler(request):
            called.append(request)
            self.assertEqual(request.url.host,'ep-test.neonauth.c-7.eu-central-1.aws.neon.tech')
            if request.url.path.endswith('/oauth2/token'):
                from urllib.parse import parse_qs
                data=parse_qs(request.content.decode())
                self.assertEqual(data['client_id'],[CLIENT])
                self.assertEqual(data['resource'],[RESOURCE])
                self.assertEqual(data['redirect_uri'],['https://'+HOST+'/auth/oauth-test/callback'])
                self.assertEqual(data['code_verifier'],['A'*43])
                self.assertEqual(data['grant_type'],['authorization_code'])
                return httpx.Response(200,json={'access_token':token,'token_type':'Bearer'})
            self.assertTrue(request.url.path.endswith('/.well-known/jwks.json'))
            return httpx.Response(200,json=jwks)
        transport=httpx.MockTransport(handler)
        original=httpx.AsyncClient
        def factory(*args,**kwargs): return original(*args,transport=transport,**kwargs)
        with patch('garminai_public.oauth_e2e_staging.httpx.AsyncClient',side_effect=factory):
            result=asyncio.run(_exchange_and_verify('B'*40,'A'*43,configuration(ENV)))
        self.assertEqual(result['result'],'OAUTH_STAGING_VERIFIED')
        self.assertFalse(result['mcp_authorized'])
        self.assertEqual(len(called),2)
        self.assertNotIn(token,str(result))

    def test_exchange_endpoint_rejects_cors_and_invalid_input(self):
        async def call(body,headers):
            payload=json.dumps(body).encode()
            received=False
            async def receive():
                nonlocal received
                if received: return {'type':'http.request','body':b'','more_body':False}
                received=True
                return {'type':'http.request','body':payload,'more_body':False}
            scope={'type':'http','method':'POST','path':'/auth/oauth-test/exchange','headers':[(k.lower().encode(),v.encode()) for k,v in headers.items()],'scheme':'https','server':(HOST,443),'client':('127.0.0.1',1)}
            return await exchange(Request(scope,receive))
        with patch.dict('os.environ',ENV,clear=True):
            headers={'Origin':'https://evil.test','Content-Type':'application/json'}
            self.assertEqual(asyncio.run(call({'code':'B'*40,'code_verifier':'A'*43},headers)).status_code,403)
            headers['Origin']='https://'+HOST
            self.assertEqual(asyncio.run(call({'code':'abc','code_verifier':'A'*43},headers)).status_code,400)
            self.assertEqual(asyncio.run(call({'code':'B'*40,'code_verifier':'A'*43,'resource':'https://evil.test'},headers)).status_code,400)
            headers['Sec-Fetch-Site']='cross-site'
            self.assertEqual(asyncio.run(call({'code':'B'*40,'code_verifier':'A'*43},headers)).status_code,403)
        with patch.dict('os.environ',{},clear=True):
            self.assertEqual(asyncio.run(call({'code':'B'*40,'code_verifier':'A'*43},headers)).status_code,404)

    def test_js_does_not_leak_auth_response(self):
        self.assertIn("history.replaceState(null, '', location.pathname)",_JS)
        self.assertIn('response_type:\'code\'',_JS)
        self.assertIn("code_challenge_method:'S256'",_JS)
        self.assertIn("params.getAll('iss')",_JS)
        self.assertIn('sessionStorage.removeItem(storageKey)',_JS)
        self.assertNotIn('localStorage',_JS)
        self.assertNotIn('innerHTML',_JS)
        self.assertNotIn('console.log',_JS)
        self.assertNotIn('client_secret',_JS)
        self.assertNotIn('access_token',_JS)


if __name__=='__main__': unittest.main()
