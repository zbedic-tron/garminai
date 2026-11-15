"""Public-safe v1.0.0 Garmin status and deliberately disabled push handlers.

This module is independently testable without starting MCP. It MUST NOT
import network clients or database adapters or acknowledge live Garmin pushes.
"""
from starlette.responses import JSONResponse
from .garmin_activity_staging import integration_status as garmin_integration_contract


async def garmin_integration_status(_request):
    return JSONResponse(garmin_integration_contract(), headers={
        'cache-control':'no-store', 'x-content-type-options':'nosniff'})


async def garmin_push_disabled(_request):
    # Never consume, parse, acknowledge or store internet-delivered Garmin
    # notifications before the official sender-auth + link contract is proven.
    # No environment variable can bypass this in v1.0.0.
    return JSONResponse({'error':'garmin_push_not_enabled',
                         'message':'Official sender authentication is still under review'},
                        status_code=503, headers={
                            'cache-control':'no-store',
                            'retry-after':'60',
                            'x-content-type-options':'nosniff'})
