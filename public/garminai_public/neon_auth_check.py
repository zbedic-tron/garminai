"""Neon Managed Better Auth v0.8.3: operator configured, read-only reachability probe.

No user session is created. Does not authorize MCP or Garmin. Never logs URLs,
headers, cookies, responses or exception messages containing sensitive values.
"""
import os
from urllib.parse import urlsplit

import httpx


def validate_auth_url(value: str) -> bool:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 512:
        return False
    try:
        p = urlsplit(value)
        host = (p.hostname or '').lower()
        return (p.scheme == 'https' and host.endswith('.neon.tech')
                and (host.endswith('.neonauth.c-7.eu-central-1.aws.neon.tech')
                     or '.neonauth.' in host)
                and not p.username and not p.password and p.port in (None, 443)
                and not p.query and not p.fragment and p.path.endswith('/auth')
                and '..' not in p.path and not any(x in value for x in ('\\', '\n', '\r', '\t')))
    except (ValueError, TypeError):
        return False


def auth_configuration_status(env=None) -> dict:
    e = os.environ if env is None else env
    raw = e.get('NEON_AUTH_URL', '')
    return {
        'neon_auth_url_configured': bool(raw),
        'neon_auth_url_valid': validate_auth_url(raw),
        'neon_auth_reachability': 'NOT_TESTED',
        'neon_session_integration_enabled': False,
        'mcp_oauth_enabled': False,
        'consent_submission_enabled': False,
    }


def check_auth_connection(env=None, transport=None) -> tuple[bool, str]:
    """Reachability only. Status 200 from get-session may mean unauthenticated null."""
    e = os.environ if env is None else env
    base = e.get('NEON_AUTH_URL', '')
    if not base:
        return False, 'NOT_CONFIGURED'
    if not validate_auth_url(base):
        return False, 'INVALID_CONFIGURATION'
    try:
        with httpx.Client(timeout=6.0, follow_redirects=False, transport=transport, trust_env=False) as client:
            response = client.get(base + '/get-session', headers={'Accept': 'application/json'})
            if response.status_code == 200:
                # No body consumed, no cookies transmitted, no identity established.
                return True, 'REACHABLE_UNAUTHENTICATED'
            if response.status_code in (401,):
                return True, 'REACHABLE_REQUIRES_SESSION'
            return False, 'UNEXPECTED_RESPONSE'
    except (httpx.HTTPError, ValueError):
        return False, 'NETWORK_OR_TLS_ERROR'


def startup_auth_report() -> None:
    ok, code = check_auth_connection()
    print('GARMINAI_NEON_AUTH_CHECK: ' + ('PASS' if ok else 'FAIL') + ' (' + code + ')', flush=True)
