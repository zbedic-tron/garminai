"""v0.8.9: token-subject isolation and negative access, no live OAuth/Garmin."""
import asyncio
import base64
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from starlette.applications import Starlette
from starlette.routing import Route

from garminai_public.demo_tenant import (
    DemoPrincipal, activities_for, detail_for, principal_from_claims, principal_from_context,
)
from garminai_public.mcp_oauth_gateway import StagingOAuthGate
from test_mcp_oauth_gateway_v088 import ENV, ISSUER, RESOURCE, CLIENT, HOST, FakeKeys


class TenantLogicTests(unittest.TestCase):
    def test_owner_ids_are_different_and_foreign_id_fails_closed(self):
        a=principal_from_claims({'iss':ISSUER,'sub':'test-A'})
        b=principal_from_claims({'iss':ISSUER,'sub':'test-B'})
        self.assertNotEqual(a, b)
        x=activities_for(a, 3)
        y=activities_for(b, 3)
        self.assertEqual(x['mode'], 'DEMO_ONLY')
        self.assertEqual(len(x['activities']),3)
        self.assertEqual(len(y['activities']),3)
        self.assertEqual(x['isolation'],'TOKEN_SUBJECT_SCOPED')
        ids_a=[v['id'] for v in x['activities']]
        ids_b=[v['id'] for v in y['activities']]
        self.assertFalse(set(ids_a) & set(ids_b))
        self.assertEqual(detail_for(a,ids_a[0])['activity']['id'],ids_a[0])
        self.assertEqual(detail_for(b,ids_a[0]),{'mode':'DEMO_ONLY','error':'unknown_demo_activity'})
        self.assertEqual(detail_for(a,ids_b[0]),{'mode':'DEMO_ONLY','error':'unknown_demo_activity'})
        self.assertEqual(detail_for(b,'demo-NONEXISTENT'),detail_for(b,ids_a[0]))
        self.assertNotIn('test-A',json.dumps(x))
        self.assertNotIn('test-B',json.dumps(y))
        self.assertNotIn(a.key,json.dumps(x))

    def test_untrusted_or_missing_context_cannot_read(self):
        for injected in (None, 'test-A', {'key':'f'*64}, object()):
            ctx=SimpleNamespace(request_context=SimpleNamespace(request=
                 SimpleNamespace(scope={'garminai.oauth_staging_principal':injected})))
            with self.subTest(injected=type(injected).__name__):
                with self.assertRaises(RuntimeError): principal_from_context(ctx)
        with self.assertRaises(RuntimeError): principal_from_context(SimpleNamespace())
        with self.assertRaises(RuntimeError): activities_for('test-A',3)
        for limit in (0,-1,11,True,'2'):
            with self.assertRaises(ValueError): activities_for(DemoPrincipal('a'*64),limit)
        for subject in ('', 'a'*257):
            with self.assertRaises(ValueError): principal_from_claims({'iss':ISSUER,'sub':subject})

    def test_iss_isolation_for_same_user_name(self):
        a=principal_from_claims({'iss':ISSUER,'sub':'same-id'})
        b=principal_from_claims({'iss':ISSUER+'/other','sub':'same-id'})
        self.assertNotEqual(activities_for(a)['activities'][0]['id'],
                            activities_for(b)['activities'][0]['id'])


class GateTwoUsers(unittest.TestCase):
    def test_two_valid_signed_subjects_are_isolated_even_under_parallel_requests(self):
        signer=ed25519.Ed25519PrivateKey.generate()
        pub=signer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        jwk={'kty':'OKP','crv':'Ed25519',
             'x':base64.urlsafe_b64encode(pub).rstrip(b'=').decode(),
             'kid':'testkey','use':'sig','alg':'EdDSA'}
        keys=FakeKeys({'keys':[jwk]})
        now=int(time.time())
        def signed(subject):
            return jwt.encode({'iss':ISSUER,'sub':subject,'aud':RESOURCE,'azp':CLIENT,
                    'scope':'openid','iat':now-5,'exp':now+120},signer,algorithm='EdDSA',
                   headers={'kid':'testkey','typ':'at+jwt'})
        # Fake downstream uses the exact ASGI context that the MCP v1 transport
        # carries into ctx.request_context.request; verifies no shared globals.
        async def fake_mcp(scope, receive, send):
            body=b''
            while True:
                msg=await receive()
                body+=msg.get('body',b'')
                if not msg.get('more_body'):break
            rpc=json.loads(body)
            principal=scope.get('garminai.oauth_staging_principal')
            self.assertIsInstance(principal,DemoPrincipal)
            self.assertFalse(any(k.lower()==b'authorization' for k,v in scope['headers']))
            operation=rpc.get('op')
            if operation=='list': result=activities_for(principal,2)
            elif operation=='detail': result=detail_for(principal,rpc['id'])
            else: result={'error':'invalid_demo_op'}
            data=json.dumps(result).encode()
            await send({'type':'http.response.start','status':200,
                        'headers':[(b'content-type',b'application/json')]})
            await send({'type':'http.response.body','body':data})
        gateway=StagingOAuthGate(fake_mcp,jwks=keys)
        app=Starlette(routes=[Route('/mcp-oauth-staging',gateway,methods=['POST'])])
        async def scenario():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                   base_url='https://'+HOST) as cli:
                async def rpc(token,payload):
                    r=await cli.post('/mcp-oauth-staging',json=payload,
                                     headers={'Authorization':'Bearer '+token,
                                              'x-demo-user':'spoofed-client-identity'})
                    return r.status_code,r.json()
                token_a,token_b=signed('user-A'),signed('user-B')
                a,b=await asyncio.gather(rpc(token_a,{'op':'list'}),rpc(token_b,{'op':'list'}))
                self.assertEqual(a[0],200);self.assertEqual(b[0],200)
                a_id=a[1]['activities'][0]['id'];b_id=b[1]['activities'][0]['id']
                self.assertNotEqual(a_id,b_id)
                owner_a,foreign_b,foreign_a,owner_b=await asyncio.gather(
                    rpc(token_a,{'op':'detail','id':a_id}),
                    rpc(token_b,{'op':'detail','id':a_id}),
                    rpc(token_a,{'op':'detail','id':b_id}),
                    rpc(token_b,{'op':'detail','id':b_id}))
                self.assertEqual(owner_a[1]['activity']['id'],a_id)
                self.assertEqual(owner_b[1]['activity']['id'],b_id)
                self.assertEqual(foreign_a[1],{'mode':'DEMO_ONLY','error':'unknown_demo_activity'})
                self.assertEqual(foreign_b[1],{'mode':'DEMO_ONLY','error':'unknown_demo_activity'})
                self.assertNotIn('user-A',json.dumps(a))
                self.assertNotIn('user-B',json.dumps(b))
        with patch.dict('os.environ',ENV,clear=True):
            asyncio.run(scenario())


if __name__=='__main__':unittest.main()
