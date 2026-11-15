"""v0.8.8: isolated authenticated MCP surface; fictional data ONLY."""
from mcp.server.fastmcp import FastMCP
from . import core

staging_mcp = FastMCP('GarminAI OAuth Staging — Fictional Data', stateless_http=True, json_response=True)


@staging_mcp.tool()
def get_sync_status() -> dict:
    """Read DEMO_ONLY status. No real Garmin or personal account data."""
    return core.status()


@staging_mcp.tool()
def get_activities(limit: int = 5) -> dict:
    """Read up to 10 fictional demo activities. Never accesses real athlete data."""
    return core.activities(limit=max(1, min(int(limit), 10)))
