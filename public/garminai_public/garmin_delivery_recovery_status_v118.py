"""Public v1.1.8 configuration-only diagnostic, NEVER checks private D1 or Neon."""
import os
from starlette.responses import JSONResponse


def recovery_status(env=None):
    e = os.environ if env is None else env
    return {
        'version': '1.1.8',
        'mode': 'SYNTHETIC_DELIVERY_RECOVERY_OPT_IN',
        'operator_enabled': e.get('GARMINAI_EDGE_RECOVERY_STAGING_ENABLED') == '1',
        'synthetic_only': True,
        'remote_recovery_flow_verified_by_this_diagnostic': False,
        'supports_d1_pending_and_idempotent_neon_retry': True,
        'simulated_faults_are_not_real_host_outages': True,
        'automatic_background_delivery_enabled': False,
        'user_delivery_status_requires_authenticated_mcp': True,
        'garmin_live_push_enabled': False,
        'mcp_real_garmin_data_enabled': False,
        'production_readiness': 'BLOCKED',
        'next': 'Use verified MCP recovery tools with synthetic-only test flag; keep Garmin Endpoint Configuration disabled.',
    }


async def public_recovery_status(_request):
    return JSONResponse(recovery_status(), headers={
        'cache-control': 'no-store', 'x-content-type-options': 'nosniff'})
