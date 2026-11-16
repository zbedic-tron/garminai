"""Read-only synthetic-only edge architecture contract for GarminAI Public 1.1.6.

No network, DB, token access, user data or inbound POST. The synthetic-only
edge_lab_v116 Worker may be manually deployed; this Render route cannot verify it.
"""
from starlette.responses import JSONResponse


def edge_lab_status() -> dict:
    return {
        "version": "1.1.6",
        "mode": "OPTIONAL_REMOTE_SYNTHETIC_EDGE_LAB",
        "edge_worker_deployed_by_garminai": False,
        "edge_lab_handles_real_garmin_push": False,
        "cloudflare_account_required_for_optional_lab": True,
        "remote_edge_deployment_verified_by_render": False,
        "cloudflare_worker_is_synthetic_only": True,
        "cloudflare_secret_required_for_writes": True,
        "production_live_garmin_push_ready": False,
        "garmin_sender_authentication_verified": False,
        "render_free_cold_start_resolved_in_production": False,
        "durable_synthetic_ack_design": "D1_COMMIT_BEFORE_HTTP_200",
        "synthetic_only_payloads": True,
        "manual_partner_approval_and_privacy_review_required": True,
        "no_payment_or_external_service_is_required_for_this_deployment": True,
        "next": "Optional: deploy synthetic-only Cloudflare Worker/D1 using the separate Free-plan lab guide; NEVER configure Garmin Endpoint Configuration.",
    }


async def public_edge_lab_status(_request):
    return JSONResponse(edge_lab_status(), headers={
        "cache-control": "no-store", "x-content-type-options": "nosniff"})
