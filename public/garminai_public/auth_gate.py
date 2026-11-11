"""Development-only HTTP bearer gate. NOT OAuth or production user authentication.

Must never be used as the identity of a Garmin athlete. Refuse MCP access when
GARMINAI_DEMO_TOKEN_SHA256 is absent, invalid or malformed. Healthz stays public.
"""
import hashlib
import hmac
import os
import re

HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authorize(headers, configured_digest=None):
    """Return (allowed, http_status). Never return/log the bearer token."""
    digest = configured_digest if configured_digest is not None else os.environ.get('GARMINAI_DEMO_TOKEN_SHA256', '')
    if not HEX64.fullmatch(digest):
        return False, 503  # fail closed until operator installs a secret
    values = [v for k, v in headers if k.lower() == b'authorization']
    if len(values) != 1:
        return False, 401
    try:
        raw = values[0].decode('ascii')
    except UnicodeDecodeError:
        return False, 401
    if not raw.startswith('Bearer '):
        return False, 401
    token = raw[7:]
    if not (32 <= len(token) <= 512) or any(c.isspace() for c in token):
        return False, 401
    return hmac.compare_digest(token_digest(token), digest.lower()), 200 if hmac.compare_digest(token_digest(token), digest.lower()) else 401


class DemoBearerGate:
    """Raw ASGI middleware guarding every HTTP and websocket request to MCP.

    A static demo key is ONLY a temporary development gate. Not per-user auth.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http', 'websocket'):
            await self.app(scope, receive, send)
            return
        allowed, status = authorize(scope.get('headers', []))
        if not allowed:
            if scope['type'] == 'websocket':
                await send({'type':'websocket.close', 'code':1008})
                return
            body = b'{"error":"demo_access_denied"}' if status == 401 else b'{"error":"demo_access_not_configured"}'
            await send({'type':'http.response.start', 'status':status,
                        'headers':[(b'content-type', b'application/json'),
                                   (b'cache-control', b'no-store'),
                                   (b'content-length', str(len(body)).encode())]})
            await send({'type':'http.response.body', 'body':body})
            return
        await self.app(scope, receive, send)
