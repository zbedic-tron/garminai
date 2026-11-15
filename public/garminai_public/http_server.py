"""GarminAI Public v1.0.2: Garmin OAuth link staging (fail closed), Neon MCP demo unchanged."""
import os
from contextlib import asynccontextmanager, AsyncExitStack
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from mcp.server.transport_security import TransportSecuritySettings

from .server import mcp
from .mcp_oauth_demo import staging_mcp
from .mcp_oauth_gateway import StagingOAuthGate
from .auth_gate import DemoBearerGate
from .readiness import get_readiness
from .db_readiness import db_configuration_status
from .db_check import startup_report
from .oauth_provider_compat import deployment_requirements
from .oauth_ui_staging import login_page, consent_page, ui_js, ui_status
from .auth_staging_poc import staging_login, staging_js
from .neon_auth_check import auth_configuration_status, startup_auth_report
from .oauth_e2e_staging import status as oauth_e2e_status, start as oauth_e2e_start, callback as oauth_e2e_callback, script as oauth_e2e_script, exchange as oauth_e2e_exchange
from .oauth_resource_staging import status as oauth_staging_status, metadata as oauth_staging_metadata
from .chatgpt_staging import status as chatgpt_status, configuration as chatgpt_configuration
from .garmin_http_staging import garmin_integration_status, garmin_push_disabled
from .garmin_link_v101 import configuration as garmin_link_configuration, start_page as garmin_connect_page, authorize as garmin_connect_authorize, callback as garmin_link_callback

hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
extra = os.environ.get("GARMINAI_ALLOWED_HOST", "").strip()
hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*", "testserver"]
origins = ["http://localhost:*", "http://127.0.0.1:*", "http://testserver"]
for value in (hostname, extra):
    if value:
        # Hostname only (no path, scheme, wildcard or newline).
        if any(char in value for char in ("/", "*", "\\", " ", "\n", "\r", ":")):
            raise ValueError("Allowed host must be a hostname, without scheme or port")
        hosts += [value, value + ":*"]
        origins += ["https://" + value]
# Official ChatGPT UI origin is permitted ONLY if the private connector is
# explicitly configured. This does not bypass our per-request JWT gate.
if chatgpt_configuration()['enabled']:
    origins.append('https://chatgpt.com')

security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=hosts,
    allowed_origins=origins,
)
mcp.settings.transport_security = security
# Do not assume the public endpoint is protected: all six tools use fictional demo data.
mcp_asgi = mcp.streamable_http_app()
# Dedicated staging MCP instance and session manager. Auth is checked by the
# outer ASGI gate BEFORE the MCP protocol handler runs; the original /mcp is
# still solely protected by DemoBearerGate.
staging_mcp.settings.transport_security = security
staging_mcp_asgi = staging_mcp.streamable_http_app()
oauth_staging_gateway = StagingOAuthGate(staging_mcp_asgi)

async def health(_request):
    return JSONResponse({"status":"ok", "version":"1.0.2", "mode":"DEMO_ONLY", "garmin_oauth":"NOT_CONNECTED", "auth":"DEMO_BEARER_GATE"})

async def index(_request):
    return JSONResponse({"project":"GarminAI Public", "version":"1.0.2", "mode":"DEMO_ONLY", "message":"Only fictional activity data. MCP endpoint: /mcp"})

async def integration_readiness(_request):
    # Only configuration booleans; never values. Not an invitation to connect Garmin yet.
    return JSONResponse({**get_readiness(), **db_configuration_status()},headers={'cache-control':'no-store'})

async def oauth_development_status(_request):
    # Static non-sensitive contract; never a promise that user login is enabled.
    return JSONResponse({**deployment_requirements(), **auth_configuration_status()}, headers={'cache-control': 'no-store'})

async def garmin_callback_disabled(_request):
    if garmin_link_configuration()['enabled']:
        return await garmin_link_callback(_request)
    return JSONResponse({'status':'not_enabled','reason':'Garmin OAuth is staged until durable user identity, encrypted token storage and consent controls are deployed'},status_code=503,headers={'cache-control':'no-store'})

@asynccontextmanager
async def lifespan(_app):
    # Operator-only diagnostic in Render Logs; no new public DB endpoint.
    # No Garmin OAuth or real-user processing is enabled by this check.
    if os.environ.get("GARMINAI_DB_CHECK_ON_START", "1") == "1":
        startup_report()
    if os.environ.get("GARMINAI_NEON_AUTH_CHECK_ON_START", "1") == "1":
        startup_auth_report()
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp.session_manager.run())
        await stack.enter_async_context(staging_mcp.session_manager.run())
        yield

app = Starlette(routes=[Route("/", index), Route("/healthz", health), Route("/integration/readiness", integration_readiness), Route("/auth/development-status", oauth_development_status), Route("/auth/oauth-ui/status", ui_status), Route("/auth/login", login_page), Route("/auth/staging/google", staging_login), Route("/auth/staging/google.js", staging_js), Route("/auth/consent", consent_page), Route("/auth/oauth-ui.js", ui_js), Route("/garmin/oauth/callback", garmin_callback_disabled), Route("/garmin/oauth/connect", garmin_connect_page), Route("/garmin/oauth/authorize", garmin_connect_authorize, methods=["POST"]), Route("/garmin/integration/status", garmin_integration_status),
    Route("/garmin/push/activities", garmin_push_disabled, methods=["POST"]),
    Route("/garmin/push/activity-details", garmin_push_disabled, methods=["POST"]),
    Route("/garmin/push/activity-files", garmin_push_disabled, methods=["POST"]),
    Route("/garmin/push/manually-updated", garmin_push_disabled, methods=["POST"]),
    Route("/garmin/push/moveiq", garmin_push_disabled, methods=["POST"]),
    Route("/garmin/push/deregistrations", garmin_push_disabled, methods=["POST"]),
    Route("/garmin/push/permissions-change", garmin_push_disabled, methods=["POST"]), Route("/auth/mcp-oauth/status", oauth_staging_status), Route("/auth/chatgpt/status", chatgpt_status), Route("/auth/oauth-test/status", oauth_e2e_status), Route("/auth/oauth-test", oauth_e2e_start), Route("/auth/oauth-test/callback", oauth_e2e_callback), Route("/auth/oauth-test.js", oauth_e2e_script), Route("/auth/oauth-test/exchange", oauth_e2e_exchange, methods=["POST"]), Route("/.well-known/oauth-protected-resource/mcp-oauth-staging", oauth_staging_metadata), Route("/.well-known/oauth-protected-resource", oauth_staging_metadata), Route("/mcp-oauth-staging", oauth_staging_gateway, methods=["GET", "POST", "DELETE"]), Mount("/", app=DemoBearerGate(mcp_asgi))], lifespan=lifespan)
