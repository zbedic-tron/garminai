import unittest
from urllib.parse import urlparse, parse_qs
from garminai_public.identity import DemoIdentityVerifier
from garminai_public.oauth_pending import PendingOAuthStore, state_digest

URL = 'postgresql://garminai_app:test@db.example/neondb?sslmode=require'

class FakeDB:
    def __init__(self): self.records = {}
    def connect(self, url): return FakeConnection(self)

class FakeConnection:
    def __init__(self, db): self.db=db; self.subject=None
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def cursor(self): return self
    def execute(self, query, params=None):
        if 'set_config(' in query:
            self.subject = params[0]
        elif 'INSERT INTO garminai.oauth_attempts' in query:
            subject,digest,nonce,encrypted,expiry=params
            assert subject == self.subject
            self.db.records[(subject,digest)] = (nonce,encrypted,expiry)
        elif 'DELETE FROM garminai.oauth_attempts' in query:
            subject,digest=params
            assert subject == self.subject
            self.row = self.db.records.pop((subject,digest), None)
        else: raise AssertionError(query)
    def fetchone(self):
        return self.row[:2] if self.row else None

class OAuthStateTest(unittest.TestCase):
    def setUp(self):
        self.v = DemoIdentityVerifier(b'x'*32)
        self.a=self.v.verify(self.v.issue_for_test('a'))
        self.b=self.v.verify(self.v.issue_for_test('b'))
        self.db=FakeDB()
        self.store=PendingOAuthStore(URL, b'K'*32, connection_factory=self.db.connect)
    def test_roundtrip_and_one_time_state(self):
        url,state=self.store.begin(self.a,client_id='demo',redirect_uri='https://example.test/garmin/oauth/callback')
        args=parse_qs(urlparse(url).query)
        self.assertEqual(args['state'][0],state)
        self.assertEqual(args['code_challenge_method'][0],'S256')
        self.assertNotIn(state,repr(self.db.records))
        self.assertIsNone(self.store.consume(self.b,state))
        verifier=self.store.consume(self.a,state)
        self.assertGreater(len(verifier),43)
        self.assertIsNone(self.store.consume(self.a,state))
    def test_reject_unverified_identity(self):
        with self.assertRaises(PermissionError):
            self.store.begin('a',client_id='demo',redirect_uri='https://example.test/cb')
    def test_invalid_state(self):
        with self.assertRaises(ValueError): state_digest('short')

if __name__=='__main__': unittest.main()
