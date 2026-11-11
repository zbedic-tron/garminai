"""AES-256-GCM envelope for future Garmin tokens. No token endpoint is enabled.

A unique random nonce is generated each encryption. Associated data binds each
blob to the verified user identity, preventing ciphertext substitution between
users. Encryption key is a separate Render secret, never a database column.
"""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .identity import VerifiedPrincipal


def load_key(encoded=None):
    value=encoded if encoded is not None else os.environ.get('GARMINAI_TOKEN_ENCRYPTION_KEY','')
    try:
        key=base64.urlsafe_b64decode(value.encode('ascii'))
    except (ValueError,UnicodeError) as exc:
        raise ValueError('Invalid token encryption key') from exc
    if len(key)!=32:
        raise ValueError('Token encryption key must contain 32 decoded bytes')
    return key


def _aad(principal):
    if not isinstance(principal,VerifiedPrincipal):
        raise PermissionError('Verified identity required')
    return ('garminai:v06:garmin-token:'+principal.subject).encode('utf-8')


class TokenVault:
    def __init__(self,key):
        if not isinstance(key,bytes) or len(key)!=32:
            raise ValueError('AES-256 key required')
        self._cipher=AESGCM(key)

    def seal(self,principal,plaintext:bytes):
        aad=_aad(principal)
        if not isinstance(plaintext,bytes) or not 1<=len(plaintext)<=16384:
            raise ValueError('Token payload size invalid')
        nonce=os.urandom(12)
        return nonce,self._cipher.encrypt(nonce,plaintext,aad)

    def open(self,principal,nonce:bytes,ciphertext:bytes):
        aad=_aad(principal)
        if not isinstance(nonce,bytes) or len(nonce)!=12:
            raise ValueError('Invalid nonce')
        return self._cipher.decrypt(nonce,ciphertext,aad)
