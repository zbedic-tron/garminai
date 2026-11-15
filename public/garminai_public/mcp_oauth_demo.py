"""v0.8.9: read-only MCP staging tools, fictional subject-scoped data only."""
from mcp.server.fastmcp import Context, FastMCP
from . import core
from .demo_tenant import principal_from_context, activities_for, detail_for

staging_mcp = FastMCP('GarminAI OAuth Staging — Fictional Data', stateless_http=True, json_response=True)


@staging_mcp.tool()
def get_sync_status(ctx: Context) -> dict:
    """Check whether this connector has synchronized Garmin data.

    Returns DEMO_ONLY / NOT_CONNECTED. This is a read-only FICTIONAL demo diagnostic, not
    real Garmin synchronization and not evidence of the user's workouts.
    Requires a verified Neon OAuth identity for every call.
    """
    principal_from_context(ctx)
    return core.status()


@staging_mcp.tool()
def get_activities(ctx: Context, limit: int = 5) -> dict:
    """List 1–10 FICTIONAL training activities for MCP demonstration.

    All records are invented and must never be presented as the caller's
    genuine Garmin workouts. Returned activity IDs are partitioned by the
    verified OAuth subject. Read-only: no network or Garmin account sync.
    """
    return activities_for(principal_from_context(ctx), limit)


@staging_mcp.tool()
def get_demo_activity_details(activity_id: str, ctx: Context) -> dict:
    """Get details of one FICTIONAL demo activity from get_activities.

    Supply activity_id exactly as returned by get_activities in this login.
    Missing/other-user IDs return unknown_demo_activity without disclosing
    whether an activity exists for a different account. Read-only.
    """
    return detail_for(principal_from_context(ctx), activity_id)
