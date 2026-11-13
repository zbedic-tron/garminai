"""Offline-verified OAuth resource-server identity contract (v0.8 staging).

IMPORTANT: NOT wired into the production /mcp route. Only an upstream trusted
OAuth/OIDC issuer may mint access tokens. Garmin access tokens are NEVER usable
as MCP access tokens. This module only verifies issuer-provided asymmetric JWTs.

JWKS retrieval, caching, key rotation, identity provider selection and real user
consent flows are deferred until a real provider is chosen and tested.
"""
import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from jwt.exceptions import PyJWTError
from .identity import VerifiedPrincipal, _MARKER

_KID = re.compile(r'^[a-zA-Z0-9._:-]{1,128}$')


class UntrustedAccessToken(PermissionError):
    """No information about token content or signing keys is exposed."""


@dataclass(frozen=True)
class VerifiedMCPIdentity:
    principal: VerifiedPrincipal
    issuer: str
    audience: str


class MCPAccessTokenVerifier:
    """Validate signed bearer tokens from exactly one configured trusted issuer.

    `jwks` must be acquired securely by the server operator and kept fresh. It is
    deliberately passed in, not fetched from attacker-controlled URLs. Only
    asymmetric RS256 signing is permitted, never HS256/none.
    """

    def __init__(self, *, issuer: str, audience: str, jwks: dict, clock_skew: int = 30):
        for value in (issuer, audience):
            if not isinstance(value, str) or urlsplit(value).scheme != 'https' or not urlsplit(value).netloc:
                raise ValueError('HTTPS issuer and resource audience required')
        if not isinstance(jwks, dict) or not isinstance(jwks.get('keys'), list):
            raise ValueError('Verified JWKS required')
        if type(clock_skew) is not int or not 0 <= clock_skew <= 60:
            raise ValueError('Clock skew out of range')
        self.issuer = issuer
        self.audience = audience
        self.skew = clock_skew
        keys = {}
        for candidate in jwks['keys']:
            if not isinstance(candidate, dict):
                continue
            kid = candidate.get('kid')
            if not isinstance(kid, str) or not _KID.fullmatch(kid):
                continue
            if candidate.get('kty') != 'RSA' or candidate.get('alg', 'RS256') != 'RS256':
                continue
            if candidate.get('use', 'sig') != 'sig':
                continue
            if kid in keys:
                raise ValueError('Duplicate key ID')
            try:
                keys[kid] = jwt.PyJWK.from_dict(candidate, algorithm='RS256').key
            except (ValueError, TypeError, PyJWTError):
                raise ValueError('Invalid issuer signing key') from None
        if not keys:
            raise ValueError('No allowed asymmetric signing keys')
        self._keys = keys

    def verify(self, bearer: str, *, required_scopes: tuple[str, ...] = ()) -> VerifiedMCPIdentity:
        if not isinstance(bearer, str) or not 32 <= len(bearer) <= 8192:
            raise UntrustedAccessToken('Invalid access token')
        try:
            header = jwt.get_unverified_header(bearer)
            if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
                raise UntrustedAccessToken('Invalid access token')
            signing_key = self._keys.get(header['kid'])
            if signing_key is None:
                raise UntrustedAccessToken('Invalid access token')
            claims = jwt.decode(
                bearer, signing_key, algorithms=['RS256'], audience=self.audience,
                issuer=self.issuer, leeway=self.skew,
                options={'require': ['iss', 'sub', 'aud', 'exp', 'iat'], 'verify_nbf': True},
            )
            # Resource permissions are taken ONLY from the verified JWT payload,
            # never from request parameters or model-supplied tool arguments.
            if required_scopes:
                scope_value = claims.get('scope')
                if isinstance(scope_value, str):
                    granted = set(scope_value.split())
                elif isinstance(scope_value, list) and all(isinstance(s, str) for s in scope_value):
                    granted = set(scope_value)
                else:
                    raise UntrustedAccessToken('Invalid access token')
                if not all(s in granted for s in required_scopes):
                    raise UntrustedAccessToken('Invalid access token')
            sub = claims.get('sub')
            if not isinstance(sub, str) or not 1 <= len(sub) <= 256 or any(ord(c) < 33 for c in sub):
                raise UntrustedAccessToken('Invalid access token')
            # Prevent accidental cross-provider collisions and do not expose raw
            # provider subjects into the database or MCP tool arguments.
            derived = 'usr_' + hashlib.sha256((self.issuer + '\x00' + sub).encode()).hexdigest()
            return VerifiedMCPIdentity(
                principal=VerifiedPrincipal(derived, _MARKER),
                issuer=self.issuer, audience=self.audience,
            )
        except (PyJWTError, ValueError, TypeError, UnicodeError, KeyError) as exc:
            raise UntrustedAccessToken('Invalid access token') from exc


def bearer_from_headers(headers: list[tuple[bytes, bytes]]) -> str:
    """Reject absent/duplicate Authorization headers and non-Bearer schemes."""
    headers_found = [v for k, v in headers if k.lower() == b'authorization']
    if len(headers_found) != 1:
        raise UntrustedAccessToken('Missing or ambiguous credentials')
    try:
        raw = headers_found[0].decode('ascii')
    except UnicodeDecodeError as exc:
        raise UntrustedAccessToken('Invalid credentials') from exc
    if not raw.startswith('Bearer ') or ' ' in raw[7:] or not raw[7:]:
        raise UntrustedAccessToken('Invalid credentials')
    return raw[7:]
