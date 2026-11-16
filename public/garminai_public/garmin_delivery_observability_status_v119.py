"""Configuration-only public diagnostics. NEVER reads private D1 or Neon rows."""
import os
from starlette.responses import JSONResponse


def observability_status(env=None):
    e = os.environ if env is None else env
    return {
        'version': '1.1.9',
        'mode': 'SYNTHETIC_RELIABILITY_READ_ONLY',
        'operator_manual_retry_enabled': e.get('GARMINAI_EDGE_RELIABILITY_STAGING_ENABLED') == '1',
        'caller_scoped_observability_via_mcp_only': True,
        'manual_retry_confirmation_required': True,
        'automatic_background_retry_enabled': False,
        'last_failure_code_recorded_in_v118_schema': False,
        'historical_latency_recorded_in_v118_schema': False,
        'cloudflare_new_migration_required': False,
        'garmin_live_push_enabled': False,
        'mcp_real_garmin_data_enabled': False,
        'production_readiness': 'BLOCKED',
        'next': 'Use authenticated MCP read-only status; manual retry only for pending synthetic receipts with operator opt-in.',
    }


async def public_observability_status(_request):
    return JSONResponse(observability_status(), headers={
        'cache-control': 'no-store', 'x-content-type-options': 'nosniff'})
