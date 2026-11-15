"""v0.9.0: isolated, opt-in Neon JWT bearer gate for fictional MCP tools.

No Garmin connectivity and no real athlete data. A separate operator opt-in is
required; the legacy /mcp demo bearer gate and database identity are unchanged.
Only the fixed Neon staging issuer is queried for public signing keys. JWTs,
subject identifiers, and Authorization headers are never logged or returned.
"""
import asyncio
import re
import time

import httpx
from starlette.responses import JSONResponse

from .oauth_e2e_staging import _check_jwt, configuration, UnsafeOAuthResponse
from .oauth_resource_staging import build_contract
from .demo_tenant import principal_from_claims

_TOKEN = re.compile(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$')
_CACHE_SECONDS = 60


def configured(env=None):
    """Flag cannot bypass the already validated fixed issuer, host, or client."""
    import os
    env = os.environ if env is None else env
    c = configuration(env)
    selected = env.get('GARMINAI_MCP_AUTH_TOOLS_STAGING_ENABLED') == '1'
    return {'requested': selected, 'enabled': selected and c['enabled'],
            'issues': c['issues'] if selected else [], 'oauth': c}


class _FixedIssuerJWKS:
    """Short-lived public-key cache, never keyed by user-controlled request values."""
    def __init__(self):
        self._issuer = ''
        self._keys = None
        self._expires = 0.0
        self._lock = asyncio.Lock()

    async def get(self, issuer):
        async with self._lock:
            now = time.monotonic()
            if self._issuer == issuer and now < self._expires and self._keys is not None:
                return self._keys
            # The issuer is checked against operator settings by configuration().
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(7.0, connect=3.0),
                                             follow_redirects=False, trust_env=False) as client:
                    r = await client.get(issuer + '/.well-known/jwks.json',
                                         headers={'Accept':'application/json'})
                    if r.status_code != 200 or len(r.content) > 65536:
                        raise ValueError('unavailable JWKS')
                    keys = r.json()
                if (not isinstance(keys, dict) or not isinstance(keys.get('keys'), list)
                        or not 1 <= len(keys['keys']) <= 32):
                    raise ValueError('invalid JWKS')
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                # Failed refresh must not silently use expired keys.
                self._keys = None
                self._expires = 0
                raise RuntimeError('JWKS_UNAVAILABLE') from exc
            self._issuer, self._keys, self._expires = issuer, keys, now + _CACHE_SECONDS
            return keys


JWKS = _FixedIssuerJWKS()


def _bearer(scope):
    found = [v for k, v in scope.get('headers', ()) if k.lower() == b'authorization']
    if len(found) != 1:
        raise UnsafeOAuthResponse('INVALID_BEARER')
    try:
        header = found[0].decode('ascii')
    except UnicodeDecodeError as exc:
        raise UnsafeOAuthResponse('INVALID_BEARER') from exc
    if not header.startswith('Bearer '):
        raise UnsafeOAuthResponse('INVALID_BEARER')
    token = header[7:]
    if not 64 <= len(token) <= 8192 or not _TOKEN.fullmatch(token):
        raise UnsafeOAuthResponse('INVALID_BEARER')
    return token


async def _reply(send, status, payload, challenge=None):
    headers = {'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
               'Referrer-Policy':'no-referrer'}
    if challenge:
        headers['WWW-Authenticate'] = challenge
    response = JSONResponse(payload, status_code=status, headers=headers)
    await response({'type':'http', 'method':'POST', 'path':'/mcp-oauth-staging',
                    'headers':[]}, None, send)


class StagingOAuthGate:
    """ASGI gate: signed, resource-bound Neon tokens only; no static demo key.

    Maps the exact existing resource URI /mcp-oauth-staging to the separate MCP
    transport's internal /mcp route. No redirect, no redirect-token leakage.
    """
    def __init__(self, mcp_app, *, jwks=None):
        self.app = mcp_app
        self.jwks = jwks or JWKS

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            if scope['type'] == 'websocket':
                await send({'type':'websocket.close','code':1008})
            return
        contract = build_contract()
        if not contract.complete:
            await _reply(send, 404, {'error':'staging_oauth_disabled'})
            return
        challenge = contract.challenge()
        opt = configured()
        if not opt['enabled']:
            await _reply(send, 401, {'error':'oauth_required','mode':'STAGING_ONLY'}, challenge)
            return
        if scope.get('path') != '/mcp-oauth-staging' or scope.get('method') not in ('POST','GET','DELETE'):
            await _reply(send, 404, {'error':'not_found'})
            return
        try:
            token = _bearer(scope)
        except UnsafeOAuthResponse:
            await _reply(send, 401, {'error':'invalid_token'}, challenge)
            return
        try:
            keys = await self.jwks.get(opt['oauth']['issuer'])
        except RuntimeError:
            await _reply(send, 503, {'error':'signing_keys_unavailable'})
            return
        try:
            # Check up to two operator-allowlisted client identities. NEVER trust
            # an unverified azp/client_id from a token to choose permissions.
            # The original E2E test client remains independently permitted.
            from .chatgpt_staging import configuration as chatgpt_configuration
            chatgpt = chatgpt_configuration()
            clients = [opt['oauth']['client_id']]
            if chatgpt['enabled']:
                clients.append(chatgpt['client_id'])
            claims = None
            for allowed_client in clients:
                try:
                    claims = _check_jwt(token, keys, issuer=opt['oauth']['issuer'],
                                        resource=opt['oauth']['resource'],
                                        client_id=allowed_client, return_claims=True)
                    break
                except UnsafeOAuthResponse:
                    continue
            if claims is None:
                raise UnsafeOAuthResponse('INVALID_CLIENT_OR_TOKEN')
            principal = principal_from_claims(claims)
        except (UnsafeOAuthResponse, ValueError, KeyError):
            await _reply(send, 401, {'error':'invalid_token'}, challenge)
            return
        # Token has been verified; do not propagate it to the demo tool runtime.
        new_scope = dict(scope)
        new_scope['headers'] = [(k,v) for k,v in scope.get('headers',())
                                if k.lower() != b'authorization']
        # Trusted per-request principal is an ASGI scope attribute, not an
        # HTTP header or caller-controlled tool argument. MCP v1 preserves the
        # Request in its tool Context; fail closed if it cannot be recovered.
        new_scope['garminai.oauth_staging_principal'] = principal
        new_scope['path'] = '/mcp'
        new_scope['raw_path'] = b'/mcp'
        new_scope['root_path'] = ''
        await self.app(new_scope, receive, send)
