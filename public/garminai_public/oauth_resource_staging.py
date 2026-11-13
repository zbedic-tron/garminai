"""v0.8.5: staging-only ChatGPT/MCP OAuth resource discovery contract.

IMPORTANT: This module cannot connect Garmin accounts or authorize tools. Its
protected endpoint deliberately returns a challenge rather than MCP results.
The current /mcp demo bearer gate is not changed by this module.

Configure a specific expected issuer, never an issuer supplied in a request.
The issuer MUST be verified against Neon's official discovery document BEFORE
switching on GARMINAI_MCP_OAUTH_STAGING_ENABLED.
"""
from dataclasses import dataclass
import os
import re
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

from .auth_staging_poc import validate_staging_auth_url
from .oauth_provider_compat import assess_provider

_HOST = re.compile(r'^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])$')
_SCOPE = "openid"  # Initial identity-only staging. No Garmin activity scope.


@dataclass(frozen=True)
class ResourceContract:
    enabled: bool
    complete: bool
    hostname: str
    issuer: str
    resource: str
    metadata_url: str
    problems: tuple[str, ...]

    def document(self) -> dict:
        if not self.complete:
            raise ValueError("Staging discovery is not configured")
        return {
            "resource": self.resource,
            "authorization_servers": [self.issuer],
            "scopes_supported": [_SCOPE],
        }

    def challenge(self) -> str:
        if not self.complete:
            raise ValueError("Staging discovery is not configured")
        return 'Bearer resource_metadata="' + self.metadata_url + '", scope="' + _SCOPE + '"'


def build_contract(env=None) -> ResourceContract:
    e = os.environ if env is None else env
    flag = e.get("GARMINAI_MCP_OAUTH_STAGING_ENABLED") == "1"
    hostname = e.get("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()
    neon_base = e.get("NEON_AUTH_STAGING_URL", "").strip()
    # This MUST be the exact `issuer` value from the provider's discovery document.
    issuer = e.get("GARMINAI_MCP_OAUTH_STAGING_ISSUER", "").strip()
    issues = []
    if not hostname or not _HOST.fullmatch(hostname) or ".." in hostname:
        issues.append("RENDER_HOST_NOT_VALID")
    if not validate_staging_auth_url(neon_base):
        issues.append("NEON_AUTH_STAGING_NOT_VALID")
    # Only the explicitly configured Neon staging issuer is accepted. Do not
    # silently substitute the production issuer or trust URL parameters.
    if not issuer or issuer != neon_base:
        issues.append("STAGING_ISSUER_NOT_VERIFIED")
    if issuer:
        p = urlsplit(issuer)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.query or p.fragment:
            issues.append("ISSUER_NOT_HTTPS")
    resource = f"https://{hostname}/mcp-oauth-staging" if not issues else ""
    metadata_url = f"https://{hostname}/.well-known/oauth-protected-resource/mcp-oauth-staging" if not issues else ""
    return ResourceContract(flag, flag and not issues, hostname, issuer, resource, metadata_url, tuple(issues))


def assess_discovery(metadata: object, *, issuer: str) -> dict:
    """Offline-only check; never fetch user-supplied URLs or trust unchecked data."""
    review = assess_provider(metadata, expected_issuer=issuer)
    problems = list(review.issues)
    if not isinstance(metadata, dict) or metadata.get("authorization_response_iss_parameter_supported") is not True:
        problems.append("issuer_parameter_not_confirmed")
    return {
        "compatible_on_paper": not problems,
        "registration_method": review.registration_method,
        "issues": problems,
        "note": "Offline metadata checks do not prove OAuth interoperability or token authorization.",
    }


async def status(_request):
    config = build_contract()
    return JSONResponse({
        "version": "0.8.5", "mode": "STAGING_ONLY",
        "oauth_provider_enabled_by_this_app": False,
        "mcp_oauth_staging_enabled": config.complete,
        "mcp_authenticated_tools_enabled": False,
        "garmin_live_data_enabled": False,
        "configuration_issues": list(config.problems) if config.enabled else [],
        "next": "Implement and test Neon OAuth login + signed oauth_query consent before enabling the provider.",
    }, headers={"Cache-Control": "no-store"})


async def metadata(_request):
    config = build_contract()
    if not config.complete:
        return JSONResponse({"error": "staging_oauth_disabled"}, status_code=404,
                            headers={"Cache-Control": "no-store"})
    return JSONResponse(config.document(), headers={"Cache-Control": "no-store"})


async def protected_stub(_request):
    """Challenge-only resource: NEVER hands out MCP tool results or identities.

    This verifies *discovery formatting*, not a real authenticated MCP call.
    The next version must add an end-to-end tested resource token verifier and
    per-tool permissions before connecting real user data.
    """
    config = build_contract()
    if not config.complete:
        return JSONResponse({"error": "staging_oauth_disabled"}, status_code=404,
                            headers={"Cache-Control": "no-store"})
    return JSONResponse({"error": "oauth_required", "mode": "STAGING_ONLY"}, status_code=401,
                        headers={"Cache-Control": "no-store", "WWW-Authenticate": config.challenge()})
