"""GarminAI Public v0.2: HTTPS-ready, *fictional demo data only*.

No auth, tokens, Garmin credentials or athlete data. Do not use for real users.
"""
import os
from contextlib import asynccontextmanager
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from mcp.server.transport_security import TransportSecuritySettings

from .server import mcp

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
    return JSONResponse({"status":"ok", "version":"0.2.0", "mode":"DEMO_ONLY", "garmin_oauth":"NOT_CONNECTED", "auth":"NOT_IMPLEMENTED"})

async def index(_request):
    return JSONResponse({"project":"GarminAI Public", "version":"0.2.0", "mode":"DEMO_ONLY", "message":"Only fictional activity data. MCP endpoint: /mcp"})

@asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield

app = Starlette(routes=[Route("/", index), Route("/healthz", health), Mount("/", app=mcp_asgi)], lifespan=lifespan)
