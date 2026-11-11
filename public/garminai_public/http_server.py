"""GarminAI Public v0.6: token-gated DEMO ONLY; not production OAuth."""
import os
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from mcp.server.transport_security import TransportSecuritySettings

from .server import mcp
from .auth_gate import DemoBearerGate
from .readiness import get_readiness
from .db_readiness import db_configuration_status

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

security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=hosts,
    allowed_origins=origins,
)
mcp.settings.transport_security = security
# Do not assume the public endpoint is protected: all six tools use fictional demo data.
mcp_asgi = mcp.streamable_http_app()

async def health(_request):
    return JSONResponse({"status":"ok", "version":"0.6.0", "mode":"DEMO_ONLY", "garmin_oauth":"NOT_CONNECTED", "auth":"DEMO_BEARER_GATE"})

async def index(_request):
    return JSONResponse({"project":"GarminAI Public", "version":"0.6.0", "mode":"DEMO_ONLY", "message":"Only fictional activity data. MCP endpoint: /mcp"})

async def integration_readiness(_request):
    # Only configuration booleans; never values. Not an invitation to connect Garmin yet.
    return JSONResponse({**get_readiness(), **db_configuration_status()},headers={'cache-control':'no-store'})

async def garmin_callback_disabled(_request):
    return JSONResponse({'status':'not_enabled','reason':'Garmin OAuth is staged until durable user identity, encrypted token storage and consent controls are deployed'},status_code=503,headers={'cache-control':'no-store'})

@asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield

app = Starlette(routes=[Route("/", index), Route("/healthz", health), Route("/integration/readiness", integration_readiness), Route("/garmin/oauth/callback", garmin_callback_disabled), Mount("/", app=DemoBearerGate(mcp_asgi))], lifespan=lifespan)
