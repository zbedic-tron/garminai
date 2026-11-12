"""Offline JWT verification: no live identities, no Garmin/network calls."""
import base64
import time
import unittest

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from garminai_public.mcp_identity import (
    MCPAccessTokenVerifier, UntrustedAccessToken, bearer_from_headers,
)
from garminai_public.identity import VerifiedPrincipal

ISS = 'https://identity.example.test/'
AUD = 'https://garminai-public-demo.onrender.com/mcp'


def b64number(n):
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length()+7)//8, 'big')).rstrip(b'=').decode()


class MCPIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = cls.private.public_key().public_numbers()
        cls.jwk = {'kty':'RSA','kid':'key-A','alg':'RS256','use':'sig',
                   'n':b64number(pub.n),'e':b64number(pub.e)}
        cls.verifier = MCPAccessTokenVerifier(issuer=ISS,audience=AUD,jwks={'keys':[cls.jwk]})

    def token(self, **overrides):
        now=int(time.time())
        claims={'iss':ISS,'aud':AUD,'sub':'runner-17','iat':now,'exp':now+300}
        claims.update(overrides)
        return jwt.encode(claims,self.private,algorithm='RS256',headers={'kid':'key-A'})

    def test_valid(self):
        ident=self.verifier.verify(self.token())
        self.assertIsInstance(ident.principal, VerifiedPrincipal)
        self.assertTrue(ident.principal.subject.startswith('usr_'))
        self.assertEqual(len(ident.principal.subject),68)

    def test_stable_and_separate_identities(self):
        a=self.verifier.verify(self.token()).principal.subject
        b=self.verifier.verify(self.token(sub='runner-18')).principal.subject
        self.assertEqual(a,self.verifier.verify(self.token()).principal.subject)
        self.assertNotEqual(a,b)

    def test_reject_wrong_issuer(self):
        with self.assertRaises(UntrustedAccessToken): self.verifier.verify(self.token(iss_='x',**{'iss':'https://evil.example/'}))

    def test_reject_wrong_resource(self):
        with self.assertRaises(UntrustedAccessToken): self.verifier.verify(self.token(aud='https://garmin.example/'))

    def test_reject_expired(self):
        with self.assertRaises(UntrustedAccessToken): self.verifier.verify(self.token(exp=int(time.time())-100))

    def test_reject_missing_subject(self):
        with self.assertRaises(UntrustedAccessToken): self.verifier.verify(self.token(sub=''))

    def test_reject_unsigned(self):
        token=jwt.encode({'iss':ISS,'aud':AUD,'sub':'runner','exp':int(time.time())+100,'iat':int(time.time())},key='',algorithm='none')
        with self.assertRaises(UntrustedAccessToken): self.verifier.verify(token)

    def test_reject_wrong_signer(self):
        other=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        t=jwt.encode({'iss':ISS,'aud':AUD,'sub':'runner','exp':int(time.time())+100,'iat':int(time.time())},other,algorithm='RS256',headers={'kid':'key-A'})
        with self.assertRaises(UntrustedAccessToken): self.verifier.verify(t)

    def test_reject_unknown_kid(self):
        t=jwt.encode({'iss':ISS,'aud':AUD,'sub':'runner','exp':int(time.time())+100,'iat':int(time.time())},self.private,algorithm='RS256',headers={'kid':'unknown'})
        with self.assertRaises(UntrustedAccessToken): self.verifier.verify(t)

    def test_reject_duplicate_jwk(self):
        with self.assertRaises(ValueError): MCPAccessTokenVerifier(issuer=ISS,audience=AUD,jwks={'keys':[self.jwk,self.jwk]})

    def test_reject_hmac_jwk(self):
        with self.assertRaises(ValueError): MCPAccessTokenVerifier(issuer=ISS,audience=AUD,jwks={'keys':[{'kid':'x','kty':'oct','k':'xyz'}]})

    def test_bearer_headers(self):
        self.assertEqual(bearer_from_headers([(b'Authorization',b'Bearer abc')]),'abc')
        with self.assertRaises(UntrustedAccessToken):bearer_from_headers([])
        with self.assertRaises(UntrustedAccessToken):bearer_from_headers([(b'Authorization',b'Bearer a'),(b'authorization',b'Bearer b')])
        with self.assertRaises(UntrustedAccessToken):bearer_from_headers([(b'Authorization',b'Basic x')])

    def test_no_public_identity_route(self):
        from pathlib import Path
        s=(Path(__file__).parents[1]/'garminai_public'/'http_server.py').read_text()
        self.assertIn('DemoBearerGate(mcp_asgi)',s)
        self.assertNotIn('MCPAccessTokenVerifier(',s)

if __name__=='__main__':unittest.main()
