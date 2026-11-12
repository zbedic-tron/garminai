"""GarminAI v0.8.1 — offline, fail-closed MCP OAuth provider compatibility checks.

NOT an OAuth authorization server, NOT active on /mcp. Never fetch issuer URLs
from users or tokens. Only operator-supplied, independently verified metadata
may be assessed. A PASS means metadata is promising, not that login works.
"""
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProviderAssessment:
    compatible_on_paper: bool
    issues: tuple[str, ...]
    registration_method: str | None


def _https_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 2048 or value != value.strip():
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'https' and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not parsed.fragment and not parsed.query
                and parsed.port in (None, 443))
    except ValueError:
        return False


def assess_provider(metadata: object, *, expected_issuer: str) -> ProviderAssessment:
    """Assess metadata; does NOT grant production permission or fetch remote URLs."""
    problems = []
    method = None
    if not _https_url(expected_issuer):
        return ProviderAssessment(False, ('invalid_expected_issuer',), None)
    if not isinstance(metadata, dict):
        return ProviderAssessment(False, ('metadata_not_object',), None)
    if metadata.get('issuer') != expected_issuer:
        problems.append('issuer_mismatch')
    for key in ('authorization_endpoint', 'token_endpoint'):
        if not _https_url(metadata.get(key)):
            problems.append(key + '_not_https')
    challenge_methods = metadata.get('code_challenge_methods_supported')
    if not isinstance(challenge_methods, list) or 'S256' not in challenge_methods:
        problems.append('pkce_s256_missing')
    response_types = metadata.get('response_types_supported')
    if not isinstance(response_types, list) or 'code' not in response_types:
        problems.append('authorization_code_flow_missing')
    methods = metadata.get('token_endpoint_auth_methods_supported', [])
    methods = methods if isinstance(methods, list) else []
    if metadata.get('client_id_metadata_document_supported') is True and ('none' in methods or 'private_key_jwt' in methods):
        method = 'CIMD'
    elif _https_url(metadata.get('registration_endpoint')):
        method = 'DCR'
    else:
        problems.append('client_registration_not_supported')
    # This check cannot certify RFC 8707 resource binding; verify issued token aud
    # and resource handling during actual end-to-end OAuth integration testing.
    return ProviderAssessment(not problems, tuple(problems), method)


def deployment_requirements() -> dict:
    """Public, non-sensitive project status. All security-critical work stays off."""
    return {
        'version': '0.8.1',
        'mode': 'STAGING_ONLY',
        'mcp_oauth_enabled': False,
        'garmin_oauth_enabled': False,
        'identity_provider_selected': False,
        'authorization_server_discovery_implemented': False,
        'end_user_login_ready': False,
        'requirements': [
            'Trusted identity provider with OAuth authorization code and PKCE S256',
            'CIMD or Dynamic Client Registration compatible with ChatGPT',
            'Protected Resource Metadata and HTTP 401 challenges',
            'JWT issuer, audience, expiry and scopes verified on each MCP request',
            'RFC 8707 resource-bound access tokens and verified subject-to-Garmin mapping',
            'End-to-end testing before real Garmin data is enabled',
        ],
    }
