"""v0.9.0: explicit ChatGPT client allowlist for fictional OAuth MCP only.

This is NOT an OAuth provider or a mechanism to register a ChatGPT client.
The operator must create a separate public Neon client in the web console,
copy the exact callback URI from ChatGPT's plugin setup and opt in.
No arbitrary callback, third-party issuer, real Garmin data, or client secrets.
"""
import os
import re
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

from .oauth_e2e_staging import configuration as oauth_configuration

_ID = re.compile(r'^[A-Za-z0-9._~-]{8,300}$')
_CALLBACK_BASE = 'https://chatgpt.com'
_STABLE = '/connector_platform_oauth_redirect'
_DYNAMIC = re.compile(r'^/connector/oauth/[A-Za-z0-9_-]{8,200}$')


def _exact_chatgpt_callback(uri):
    """Allow only documented ChatGPT HTTPS callback formats, never user URLs."""
    if not isinstance(uri, str) or not 30 <= len(uri) <= 512 or uri != uri.strip():
        return False
    try:
        p = urlsplit(uri)
        return (p.scheme == 'https' and p.netloc == 'chatgpt.com' and
                not p.username and not p.password and not p.query and not p.fragment and
                (p.path == _STABLE or bool(_DYNAMIC.fullmatch(p.path))) and
                uri == _CALLBACK_BASE + p.path)
    except ValueError:
        return False


def configuration(env=None):
    e = os.environ if env is None else env
    requested = e.get('GARMINAI_CHATGPT_MCP_STAGING_ENABLED') == '1'
    client = e.get('GARMINAI_CHATGPT_OAUTH_CLIENT_ID', '').strip()
    callback = e.get('GARMINAI_CHATGPT_OAUTH_CALLBACK', '').strip()
    from .mcp_oauth_gateway import configured as gate_configured
    # Gate's configuration returns the validated staging issuer, audience and
    # the existing independent operator opt-in. Does NOT depend on this module.
    gate = gate_configured(e)
    oauth = oauth_configuration(e)
    issues = []
    if requested:
        if not _ID.fullmatch(client) or client == oauth.get('client_id'):
            issues.append('CHATGPT_CLIENT_ID_INVALID_OR_REUSED')
        if not _exact_chatgpt_callback(callback):
            issues.append('CHATGPT_CALLBACK_INVALID')
        if not gate['enabled'] or not oauth['enabled']:
            issues.append('EXISTING_OAUTH_STAGING_NOT_READY')
        if oauth.get('origin') != 'https://garminai-public-demo.onrender.com':
            issues.append('UNEXPECTED_STAGING_HOST')
    return {
        'requested': requested,
        'enabled': requested and not issues,
        'issues': issues,
        'client_id': client if requested and not issues else '',
        'callback': callback if requested and not issues else '',
    }


async def status(_request):
    c = configuration()
    from .oauth_resource_staging import build_contract
    contract = build_contract()
    return JSONResponse({
        'version': '0.9.0', 'mode': 'CHATGPT_PRIVATE_STAGING_ONLY',
        'chatgpt_connector_enabled': c['enabled'],
        'chatgpt_connector_requested': c['requested'],
        'chatgpt_config_issues': c['issues'],
        'mcp_url': contract.resource if contract.complete else None,
        'resource_metadata_url': contract.metadata_url if contract.complete else None,
        'expected_neon_registration': 'SEPARATE_PUBLIC_CLIENT_WITH_EXACT_CHATGPT_CALLBACK',
        'oauth_registration_performed_by_app': False,
        'real_garmin_access_enabled': False,
        'public_plugin_published': False,
    }, headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})
