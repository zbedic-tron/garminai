"""v0.8.9: read-only MCP staging tools, fictional subject-scoped data only."""
from mcp.server.fastmcp import Context, FastMCP
from . import core
from .demo_tenant import principal_from_context, activities_for, detail_for

staging_mcp = FastMCP('GarminAI OAuth Staging — Fictional Data', stateless_http=True, json_response=True)


@staging_mcp.tool()
def get_sync_status(ctx: Context) -> dict:
    """Read DEMO_ONLY status. Requires verified Neon identity; no real Garmin."""
    principal_from_context(ctx)
    return core.status()


@staging_mcp.tool()
def get_activities(ctx: Context, limit: int = 5) -> dict:
    """Read 1–10 fictional activities, isolated by signed OAuth subject."""
    return activities_for(principal_from_context(ctx), limit)


@staging_mcp.tool()
def get_demo_activity_details(activity_id: str, ctx: Context) -> dict:
    """Read fictional activity ONLY if its ID belongs to this token subject."""
    return detail_for(principal_from_context(ctx), activity_id)
