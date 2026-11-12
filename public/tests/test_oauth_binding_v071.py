"""Identity binding, expiry, and replay tests with NO external Garmin/Neon calls."""
import unittest
from datetime import datetime, timezone
from garminai_public.oauth_binding import IdentityBoundGarminFlow
from garminai_public.identity import DemoIdentityVerifier
from garminai_public.oauth_pending import PendingOAuthStore
from test_oauth_pending_v07 import FakeDB, FakeConnection, URL

class TimedFakeConnection(FakeConnection):
    def execute(self, query, params=None):
        if 'DELETE FROM garminai.oauth_attempts' in query:
            subject, digest = params
            assert subject == self.subject
            rec = self.db.records.get((subject, digest))
            self.row = None
            if rec is not None and rec[2].timestamp() > self.db.now:
                self.row = self.db.records.pop((subject, digest))
        else:
            super().execute(query, params)

class TimedFakeDB(FakeDB):
    def __init__(self, now):
        super().__init__()
        self.now=now
    def connect(self, url):
        return TimedFakeConnection(self)

class IdentityBindingTests(unittest.TestCase):
    def setUp(self):
        self.now=1763000000
        self.verifier=DemoIdentityVerifier(b'Q'*32,clock=lambda:self.now)
        self.a=self.verifier.verify(self.verifier.issue_for_test('runner_a'))
        self.b=self.verifier.verify(self.verifier.issue_for_test('runner_b'))
        self.db=TimedFakeDB(self.now)
        store=PendingOAuthStore(URL,b'Y'*32,connection_factory=self.db.connect,clock=lambda:self.db.now)
        self.flow=IdentityBoundGarminFlow(store)

    def start(self,principal=None):
        return self.flow.start(principal or self.a,client_id='test-client',redirect_uri='https://example.test/garmin/oauth/callback')

    def test_valid_callback_once(self):
        _url,state=self.start()
        result=self.flow.resolve_callback(self.a,state=state,code='test_code')
        self.assertEqual(result.subject,'runner_a')
        self.assertGreaterEqual(len(result.pkce_verifier),43)
        with self.assertRaises(PermissionError):
            self.flow.resolve_callback(self.a,state=state,code='test_code')

    def test_wrong_user_cannot_consume(self):
        _url,state=self.start()
        with self.assertRaises(PermissionError):
            self.flow.resolve_callback(self.b,state=state,code='test_code')
        self.assertEqual(self.flow.resolve_callback(self.a,state=state,code='test_code').subject,'runner_a')

    def test_expired_state_rejected(self):
        _url,state=self.start()
        self.db.now += 601
        with self.assertRaises(PermissionError):
            self.flow.resolve_callback(self.a,state=state,code='test_code')

    def test_missing_identity_denied(self):
        with self.assertRaises(PermissionError):self.flow.start('runner_a',client_id='test',redirect_uri='https://example.test/cb')
        _url,state=self.start()
        with self.assertRaises(PermissionError):self.flow.resolve_callback('runner_a',state=state,code='test_code')

    def test_denial_consumes_state(self):
        _url,state=self.start()
        with self.assertRaises(PermissionError):
            self.flow.resolve_callback(self.a,state=state,error='access_denied')
        with self.assertRaises(PermissionError):
            self.flow.resolve_callback(self.a,state=state,code='test_code')

    def test_missing_code_consumes_state(self):
        _url,state=self.start()
        with self.assertRaises(ValueError):self.flow.resolve_callback(self.a,state=state)
        with self.assertRaises(PermissionError):self.flow.resolve_callback(self.a,state=state,code='test_code')

    def test_start_requires_https_callback(self):
        with self.assertRaises(ValueError):
            self.flow.start(self.a,client_id='test',redirect_uri='http://insecure.test/cb')

    def test_no_public_oauth_route_enabled(self):
        # Inspect the declared routes without importing optional MCP runtime.
        from pathlib import Path
        source=(Path(__file__).parents[1]/'garminai_public'/'http_server.py').read_text()
        self.assertIn('Route("/garmin/oauth/callback"',source)
        self.assertNotIn('Route("/garmin/oauth/start"',source)

if __name__=='__main__':unittest.main()
