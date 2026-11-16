"""v1.1.7 public READ-ONLY diagnostic, no network or database queries."""
from __future__ import annotations
import os
from starlette.responses import JSONResponse


def bridge_status(env=None):
    e = os.environ if env is None else env
    return {
        'version':'1.1.7', 'mode':'SYNTHETIC_EDGE_TO_NEON_OPT_IN',
        'operator_enabled': e.get('GARMINAI_EDGE_BRIDGE_STAGING_ENABLED') == '1',
        'live_garmin_push_enabled':False,
        'mcp_real_garmin_data_enabled':False,
        'data_sharing_with_ai_enabled':False,
        'no_public_render_bridge_post_route':True,
        'render_pull_only_via_verified_mcp':True,
        'external_d1_deployment_not_verified_by_this_route':True,
        'neon_durable_bridge_not_verified_by_this_route':True,
        'garmin_sender_authentication_verified':False,
        'production_readiness':'BLOCKED',
        'next':'Use the verified MCP tool for one synthetic-only D1-to-Neon rehearsal; disable operator flag afterwards.',
    }


async def public_bridge_status(_request):
    return JSONResponse(bridge_status(), headers={
        'cache-control':'no-store', 'x-content-type-options':'nosniff'})
