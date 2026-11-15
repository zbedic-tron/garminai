"""v1.1.4: public-safe, read-only Garmin push operational risk report.

This module is a diagnostic *not* an authentication module, health monitor,
proof of IP provenance, reliable background worker, or permission to ingest.
It contains no private Garmin CIDRs, licenses, credentials, user identifiers,
or live request headers. Never wire it to the Garmin push POST handlers.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from starlette.responses import JSONResponse


# These are DEPLOYMENT BLOCKERS, not dynamically measured booleans.
# The Render Free plan cannot guarantee timely cold-start responses and has
# no web-service inbound-IP allowlist. Trusted original-IP provenance was
# not established for our deployment. Never allow env vars to override them.
BLOCKERS = (
    "TRUSTED_GARMIN_SENDER_PROVENANCE_UNVERIFIED",
    "RENDER_FREE_COLD_START_DEADLINE_NOT_GUARANTEED",
    "PUBLIC_WEBHOOK_DURABLE_ACK_PATH_NOT_VALIDATED",
    "GARMIN_TERMS_AI_AND_THIRD_PARTY_SHARING_REVIEW_PENDING",
)


def readiness_report(env: Mapping[str, str] | None = None) -> dict:
    """Read-only policy snapshot; no DB, network, cache or IP-header access.

    Even if an operator sets a legacy enable flag, a live Garmin push request
    remains blocked. The report deliberately does not inspect or expose any
    credential values or personally identifying information.
    """
    env = os.environ if env is None else env
    rehearsal = env.get("GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED") == "1"
    accidentally_requested = env.get("GARMINAI_GARMIN_PUSH_ENABLED") == "1"
    return {
        "version": "1.1.4",
        "mode": "READ_ONLY_DIAGNOSTIC",
        "readiness": "BLOCKED",
        "live_garmin_push_enabled": False,
        "trusted_source_provenance_verified": False,
        "garmin_sender_cryptographically_authenticated": False,
        "response_deadline_guaranteed_on_free_hosting": False,
        "durable_live_delivery_verified": False,
        "mcp_real_garmin_data_enabled": False,
        "rehearsal_operator_flag_enabled": rehearsal,
        "rehearsal_flag_should_be_disabled_after_test": rehearsal,
        "live_push_requested_by_legacy_flag": accidentally_requested,
        "legacy_flag_does_not_enable_push": True,
        "synthetic_neon_test": "NOT_RERUN_BY_THIS_DIAGNOSTIC",
        "blocking_reasons": list(BLOCKERS),
        "next": ("Keep Garmin Endpoint Configuration disabled, restore rehearsal "
                 "flag to 0, and do not trust forwarded headers as sender proof."),
    }


async def public_readiness(_request):
    return JSONResponse(readiness_report(), headers={
        "cache-control": "no-store", "x-content-type-options": "nosniff"})
