"""DEVELOPMENT-ONLY verified test identities. NOT Garmin OAuth or ChatGPT OAuth.

Identity must be established by signature verification, never user_id headers
or tool arguments. No identity credentials are used by the public MCP in v0.4.
"""
import base64
import hashlib
import hmac
import json
import re
import time

_MARKER = object()
_SUB_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$')

class VerifiedPrincipal:
    __slots__ = ('_subject', '_marker')
    def __init__(self, subject: str, marker: object):
        if marker is not _MARKER or not isinstance(subject, str) or not _SUB_RE.fullmatch(subject):
            raise PermissionError('A verified identity is required')
        self._subject = subject
        self._marker = marker
    @property
    def subject(self):
        return self._subject

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))

class DemoIdentityVerifier:
    """Self-contained HMAC fixture for security tests; do NOT connect to /mcp."""
    def __init__(self, secret: bytes, *, issuer='garminai-test', audience='garminai-test-api', clock=None):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError('At least 32 bytes of independent test secret required')
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._clock = clock or time.time

    def issue_for_test(self, subject: str, ttl_seconds: int = 300) -> str:
        if not isinstance(subject, str) or not _SUB_RE.fullmatch(subject):
            raise ValueError('Invalid subject')
        if not (1 <= ttl_seconds <= 3600):
            raise ValueError('Invalid TTL')
        now=int(self._clock())
        payload=json.dumps({'sub':subject,'iss':self._issuer,'aud':self._audience,
                            'iat':now,'exp':now+ttl_seconds},separators=(',',':'),sort_keys=True).encode()
        encoded=_b64(payload)
        mac=hmac.new(self._secret,encoded.encode('ascii'),hashlib.sha256).digest()
        return encoded+'.'+_b64(mac)

    def verify(self, token: str) -> VerifiedPrincipal:
        if not isinstance(token,str) or len(token)>2048 or token.count('.')!=1:
            raise PermissionError('Invalid credential')
        try:
            encoded,signature=token.split('.')
            expected=hmac.new(self._secret,encoded.encode('ascii'),hashlib.sha256).digest()
            supplied=_unb64(signature)
            if not hmac.compare_digest(expected,supplied):
                raise PermissionError('Invalid credential')
            claims=json.loads(_unb64(encoded))
            now=int(self._clock())
            if not isinstance(claims,dict) or claims.get('iss')!=self._issuer or claims.get('aud')!=self._audience:
                raise PermissionError('Invalid identity context')
            if type(claims.get('exp')) is not int or type(claims.get('iat')) is not int:
                raise PermissionError('Invalid lifetime')
            if not (now < claims['exp'] <= now+3600) or claims['iat']>now+30:
                raise PermissionError('Expired or future credential')
            return VerifiedPrincipal(claims.get('sub'),_MARKER)
        except (ValueError,UnicodeError,TypeError,KeyError,OverflowError) as exc:
            raise PermissionError('Invalid credential') from exc
