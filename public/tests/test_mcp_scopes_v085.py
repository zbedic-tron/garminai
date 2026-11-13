"""v0.8.5 verified issuer/resource/scope contract (offline, no Garmin)."""
import base64
import time
import unittest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from garminai_public.mcp_identity import MCPAccessTokenVerifier, UntrustedAccessToken


def b64(n):
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length()+7)//8,'big')).rstrip(b'=').decode()

class ScopeVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        numbers=cls.private.public_key().public_numbers()
        jwk={'kty':'RSA','kid':'staging','alg':'RS256','use':'sig','n':b64(numbers.n),'e':b64(numbers.e)}
        cls.iss='https://id.example.test/auth'
        cls.aud='https://garminai-public-demo.onrender.com/mcp-oauth-staging'
        cls.verifier=MCPAccessTokenVerifier(issuer=cls.iss,audience=cls.aud,jwks={'keys':[jwk]})

    def token(self, **kw):
        now=int(time.time())
        claims=dict(iss=self.iss,aud=self.aud,sub='test-runner',iat=now,exp=now+120,scope='openid profile')
        claims.update(kw)
        return jwt.encode(claims,self.private,algorithm='RS256',headers={'kid':'staging'})

    def test_openid_accepted(self):
        self.assertTrue(self.verifier.verify(self.token(),required_scopes=('openid',)).principal.subject.startswith('usr_'))

    def test_wrong_scope_rejected(self):
        with self.assertRaises(UntrustedAccessToken):
            self.verifier.verify(self.token(),required_scopes=('garminai.activities.read',))

    def test_missing_scope_rejected(self):
        with self.assertRaises(UntrustedAccessToken):
            self.verifier.verify(self.token(scope=None),required_scopes=('openid',))

    def test_wrong_resource_rejected_even_with_correct_scope(self):
        with self.assertRaises(UntrustedAccessToken):
            self.verifier.verify(self.token(aud='https://another.example.test/mcp'),required_scopes=('openid',))

    def test_scope_list_accepted(self):
        self.assertIsNotNone(self.verifier.verify(self.token(scope=['openid','profile']),required_scopes=('openid',)))

if __name__=='__main__': unittest.main()
