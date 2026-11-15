"""Offline safety tests: no real Garmin account, no DB mutations."""
import asyncio
import base64
import os
import secrets
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs,unquote
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from garminai_public.identity import (principal_from_verified_neon_claims,
                                      principal_from_sealed_link, DemoIdentityVerifier)
from garminai_public.garmin_link_v101 import (
    configuration, issue_ticket, validate_ticket, make_state, validate_state,
    start_page, authorize, callback, connect_link_from_context,
    status_from_context, _permission_list, CALLBACK,
)
from garminai_public.garmin_oauth import GARMIN_TOKEN_URL

def _handoff_url(page):
    import re, html
    target = re.search(r'href="(https://connect\.garmin\.com/oauth2Confirm\?[^"]+)"',page)
    if not target:
        raise AssertionError('Missing official Garmin fallback navigation')
    return html.unescape(target.group(1))


K=secrets.token_bytes(32)
GOOD={'GARMINAI_GARMIN_LINK_STAGING_ENABLED':'1','GARMIN_CLIENT_ID':'mock-garmin-client',
      'GARMIN_CLIENT_SECRET':'mock-private-secret','GARMIN_REDIRECT_URI':CALLBACK,
      'DATABASE_URL':'postgresql://runtime:secret@database.example/db?sslmode=require',
      'GARMINAI_TOKEN_ENCRYPTION_KEY':base64.urlsafe_b64encode(K).decode()}
ALICE={'iss':'https://issuer.example/oauth', 'sub':'alice'}
BOB={'iss':'https://issuer.example/oauth', 'sub':'bob'}

class TestGarminLink(unittest.TestCase):
    def setUp(self):
        self.alice=principal_from_verified_neon_claims(ALICE)
        self.bob=principal_from_verified_neon_claims(BOB)

    def test_stable_real_neon_principal_not_demo_process_local(self):
        self.assertEqual(self.alice.subject,principal_from_verified_neon_claims(ALICE).subject)
        self.assertNotEqual(self.alice.subject,self.bob.subject)
        self.assertEqual(len(self.alice.subject),64)
        self.assertNotIn('alice',self.alice.subject)
        fake=DemoIdentityVerifier(b'x'*40)
        self.assertNotEqual(self.alice.subject,fake.verify(fake.issue_for_test('alice')).subject)

    def test_disabled_even_if_other_staging_is_on(self):
        c=configuration({**GOOD,'GARMINAI_GARMIN_LINK_STAGING_ENABLED':'0'})
        self.assertFalse(c['enabled'])
        self.assertEqual(c['issues'],[])
        for missing in ('GARMIN_CLIENT_ID','GARMIN_CLIENT_SECRET','GARMINAI_TOKEN_ENCRYPTION_KEY','DATABASE_URL'):
            c=configuration({**GOOD,missing:''})
            self.assertFalse(c['enabled'],missing)
            self.assertTrue(c['issues'],missing)
        c=configuration({**GOOD,'GARMIN_REDIRECT_URI':'https://evil.example/cb'})
        self.assertFalse(c['enabled'])
        self.assertFalse(c['push_enabled'])
        self.assertFalse(c['real_mcp_enabled'])

    def test_ticket_encrypted_bound_to_principal_and_expires(self):
        ticket=issue_ticket(self.alice,key=K,now=1000)
        data=validate_ticket(ticket,key=K,now=1200)
        self.assertEqual(data['subject'],self.alice.subject)
        self.assertNotIn(self.alice.subject,ticket)
        self.assertNotIn('alice',ticket)
        with self.assertRaises(ValueError): validate_ticket(ticket,key=K,now=1600)
        with self.assertRaises(ValueError): validate_ticket(ticket[:-3]+'abc',key=K,now=1001)
        with self.assertRaises(ValueError): validate_ticket(ticket,key=secrets.token_bytes(32),now=1001)

    def test_state_browser_bound_subject_verifier_and_expiry(self):
        cookie=secrets.token_urlsafe(32)
        state=make_state(self.alice,'A'*64,cookie,key=K,now=1000)
        payload=validate_state(state,cookie,key=K,now=1100)
        self.assertEqual(payload['subject'],self.alice.subject)
        self.assertEqual(payload['verifier'],'A'*64)
        self.assertNotIn('alice',state)
        with self.assertRaises(ValueError): validate_state(state,'different-cookie',key=K,now=1100)
        with self.assertRaises(ValueError): validate_state(state,cookie,key=K,now=1700)
        with self.assertRaises(ValueError): validate_state(state[:20]+('A' if state[20]!='A' else 'B')+state[21:],cookie,key=K,now=1100)

    def test_forbid_caller_supplied_identity(self):
        ctx=SimpleNamespace(request_context=SimpleNamespace(request=SimpleNamespace(scope={})))
        with patch.dict(os.environ,GOOD,clear=False):
            with self.assertRaises(PermissionError): connect_link_from_context(ctx)
            with self.assertRaises(PermissionError): status_from_context(ctx)
            ctx.request_context.request.scope['garminai.verified_garmin_principal']=self.alice
            with patch('garminai_public.garmin_link_v101._assert_database_ready'):
                link=connect_link_from_context(ctx)
            self.assertEqual(link['status'],'READY_FOR_USER_CONFIRMATION')
            self.assertIn('/garmin/oauth/connect?ticket=',link['url'])
            self.assertNotIn('alice',link['url'])

    def test_permissions_must_include_activity_export(self):
        self.assertEqual(_permission_list(['ACTIVITY_EXPORT']),['ACTIVITY_EXPORT'])
        self.assertEqual(_permission_list({'permissions':['ACTIVITY_EXPORT']}),['ACTIVITY_EXPORT'])
        for value in ({'other':True},'ACTIVITY_EXPORT',['ACTIVITY_EXPORT',1]):
            with self.assertRaises(ValueError): _permission_list(value)

    def test_authorization_and_callback_stay_disabled_by_default(self):
        app=Starlette(routes=[Route('/garmin/oauth/connect',start_page),
            Route('/garmin/oauth/authorize',authorize,methods=['POST']),
            Route('/garmin/oauth/callback',callback)])
        with patch.dict(os.environ,{'GARMINAI_GARMIN_LINK_STAGING_ENABLED':'0'},clear=False):
            with TestClient(app) as client:
                self.assertEqual(client.get('/garmin/oauth/connect').status_code,503)
                self.assertEqual(client.post('/garmin/oauth/authorize').status_code,503)
                self.assertEqual(client.get('/garmin/oauth/callback').status_code,503)

    def test_browser_confirmation_ends_form_post_before_garmin_navigation(self):
        # Chromium enforces form-action throughout redirected form submissions.
        # End POST with a 200 HTML response; a meta refresh starts fresh navigation.
        # Keep the form same-origin-only and forbid scripts/external resources.
        app=Starlette(routes=[Route('/garmin/oauth/connect',start_page),
            Route('/garmin/oauth/authorize',authorize,methods=['POST'])])
        with patch.dict(os.environ,GOOD,clear=False):
            with TestClient(app,base_url='https://garminai-public-demo.onrender.com') as client:
                ticket=issue_ticket(self.alice,key=K)
                page=client.get('/garmin/oauth/connect',params={'ticket':ticket})
                self.assertEqual(page.status_code,200)
                csp=page.headers['content-security-policy']
                self.assertIn("form-action 'self';",csp)
                self.assertNotIn('https://connectapi.garmin.com',csp)
                self.assertIn("script-src 'none'",csp)
                self.assertIn('frame-ancestors',csp)
                # Successful browser POST ends on our origin with an HTML handoff.
                import re
                csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
                rsp=client.post('/garmin/oauth/authorize',data={'csrf':csrf,'ticket':ticket},follow_redirects=False)
                self.assertEqual(rsp.status_code,200)
                self.assertNotIn('location',rsp.headers)
                self.assertIn('http-equiv="refresh"',rsp.text)
                self.assertIn('href="https://connect.garmin.com/oauth2Confirm?',rsp.text)
                self.assertIn("form-action 'self';",rsp.headers['content-security-policy'])
                self.assertEqual(rsp.headers['cache-control'],'no-store, max-age=0')
                self.assertEqual(rsp.headers['referrer-policy'],'no-referrer')
                # Invalid confirmation returns an error page with stricter CSP.
                bad=client.post('/garmin/oauth/authorize',data={'csrf':'bad','ticket':ticket})
                self.assertEqual(bad.status_code,400)
                self.assertIn("form-action 'self';",bad.headers['content-security-policy'])
                self.assertNotIn('https://connect.garmin.com',bad.headers['content-security-policy'])

    def test_handoff_rejects_untrusted_navigation_target(self):
        from garminai_public.garmin_link_v101 import _garmin_navigation_page
        for target in ('https://evil.example/oauth2Confirm',
                       'https://connect.garmin.com.evil.example/oauth2Confirm',
                       'http://connect.garmin.com/oauth2Confirm',
                       'https://connect.garmin.com/other',
                       'https://user@connect.garmin.com/oauth2Confirm'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                _garmin_navigation_page(target)

    def test_browser_confirmation_then_garmin_redirect_no_network_or_secrets(self):
        app=Starlette(routes=[Route('/garmin/oauth/connect',start_page),
            Route('/garmin/oauth/authorize',authorize,methods=['POST'])])
        with patch.dict(os.environ,GOOD,clear=False):
            with TestClient(app,base_url='https://garminai-public-demo.onrender.com') as client:
                ticket=issue_ticket(self.alice,key=K)
                start=client.get('/garmin/oauth/connect',params={'ticket':ticket})
                self.assertEqual(start.status_code,200)
                self.assertIn('Nastavi na Garmin',start.text)
                self.assertIn('no-referrer',start.headers['referrer-policy'])
                self.assertNotIn('mock-private-secret',start.text)
                import re
                csrf=re.search(r'name="csrf" value="([^"]+)"',start.text).group(1)
                answer=client.post('/garmin/oauth/authorize',data={'csrf':csrf,'ticket':ticket},follow_redirects=False)
                self.assertEqual(answer.status_code,200)
                self.assertNotIn('location',answer.headers)
                url=urlsplit(_handoff_url(answer.text))
                self.assertEqual(url.hostname,'connect.garmin.com')
                p=parse_qs(url.query)
                self.assertEqual(p['redirect_uri'],[CALLBACK])
                self.assertEqual(p['code_challenge_method'],['S256'])
                self.assertNotIn(self.alice.subject,str(p))
                self.assertNotIn('mock-private-secret',str(p))
                self.assertTrue(p['state'][0])
                no_cookie=TestClient(app,base_url='https://garminai-public-demo.onrender.com')
                self.assertEqual(no_cookie.post('/garmin/oauth/authorize',data={'csrf':csrf,'ticket':ticket}).status_code,400)

    def test_garmin_token_endpoint_matches_official_partner_spec(self):
        self.assertEqual(GARMIN_TOKEN_URL,'https://connectapi.garmin.com/di-oauth2-service/oauth/token')

    def test_full_browser_flow_with_fake_provider_and_one_time_state(self):
        """No network, DB or Garmin data; tests only safe linking transitions."""
        app=Starlette(routes=[Route('/garmin/oauth/connect',start_page),
             Route('/garmin/oauth/authorize',authorize,methods=['POST']),
             Route('/garmin/oauth/callback',callback)])
        used=set()
        seen={}
        class FakeResponse:
            def __init__(self,obj):self.obj=obj
            def raise_for_status(self): pass
            def json(self):return self.obj
        class FakeClient:
            def __init__(self, **kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*a):pass
            async def post(self,url,**kwargs):
                self_case.assertEqual(url,GARMIN_TOKEN_URL)
                self_case.assertEqual(kwargs['data']['client_secret'],'mock-private-secret')
                self_case.assertTrue(kwargs['data']['code_verifier'])
                return FakeResponse({'access_token':'FAKE_ACCESS_SECRET',
                                     'refresh_token':'FAKE_REFRESH_SECRET','expires_in':3600})
            async def get(self,url,**kwargs):
                self_case.assertEqual(kwargs['headers']['Authorization'],'Bearer FAKE_ACCESS_SECRET')
                if url.endswith('/user/id'): return FakeResponse({'userId':'FAKE_GARMIN_ID'})
                return FakeResponse(['ACTIVITY_EXPORT'])
        def consume(principal,state):
            if state in used: raise PermissionError('REPLAYED')
            used.add(state)
        def store(principal,uid,token,perms,key):
            seen['subject']=principal.subject
            seen['id']=uid
            seen['perms']=perms
            seen['token']=token
        self_case=self
        with patch.dict(os.environ,GOOD,clear=False), \
             patch('garminai_public.garmin_link_v101._consume_callback',side_effect=consume), \
             patch('garminai_public.garmin_link_v101._store_link',side_effect=store), \
             patch('garminai_public.garmin_link_v101.httpx.AsyncClient',FakeClient):
            with TestClient(app,base_url='https://garminai-public-demo.onrender.com') as client:
                ticket=issue_ticket(self.alice,key=K)
                page=client.get('/garmin/oauth/connect',params={'ticket':ticket})
                import re
                csrf=re.search(r'name="csrf" value="([^"]+)"',page.text).group(1)
                redirect=client.post('/garmin/oauth/authorize',data={'csrf':csrf,'ticket':ticket},follow_redirects=False)
                self.assertEqual(redirect.status_code,200)
                state=parse_qs(urlsplit(_handoff_url(redirect.text)).query)['state'][0]
                result=client.get('/garmin/oauth/callback',params={'state':state,'code':'FAKE_CODE_123456'})
                self.assertEqual(result.status_code,200)
                self.assertIn('povezan',result.text)
                self.assertNotIn('FAKE_ACCESS_SECRET',result.text)
                self.assertNotIn('FAKE_REFRESH_SECRET',result.text)
                self.assertNotIn('FAKE_GARMIN_ID',result.text)
                self.assertEqual(seen['subject'],self.alice.subject)
                self.assertEqual(seen['perms'],['ACTIVITY_EXPORT'])
                self.assertEqual(seen['id'],'FAKE_GARMIN_ID')
                replay=client.get('/garmin/oauth/callback',params={'state':state,'code':'FAKE_CODE_123456'})
                self.assertEqual(replay.status_code,400)

    def test_callback_rejects_missing_browser_cookie_before_provider_call(self):
        app=Starlette(routes=[Route('/garmin/oauth/callback',callback)])
        cookie=secrets.token_urlsafe(32)
        state=make_state(self.alice,'B'*64,cookie,key=K)
        with patch.dict(os.environ,GOOD,clear=False), \
             patch('garminai_public.garmin_link_v101._consume_callback') as consume:
            with TestClient(app,base_url='https://garminai-public-demo.onrender.com') as client:
                res=client.get('/garmin/oauth/callback',params={'code':'CODE_12345678','state':state})
                self.assertEqual(res.status_code,400)
                consume.assert_not_called()

    def test_migration_rls_and_no_actual_push(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        sql=(root/'sql/003_garmin_oauth_used_states.sql').read_text()
        self.assertIn('FORCE ROW LEVEL SECURITY',sql)
        self.assertIn('garminai.subject',sql)
        self.assertIn('GRANT SELECT, INSERT',sql)
        server=(root/'garminai_public/http_server.py').read_text()
        self.assertIn('garmin_push_disabled, methods=["POST"]',server)
        self.assertNotIn('garmin_pull_activities',server)

if __name__=='__main__':unittest.main()
