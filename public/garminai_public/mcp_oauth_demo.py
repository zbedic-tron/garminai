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


@staging_mcp.tool()
def get_garmin_connection_link(ctx: Context) -> dict:
    """Request a private 10-minute Garmin Connect authorization link.

    Only works when the operator has explicitly enabled separate Garmin linking
    and durable encrypted Neon storage. Opening the link requires explicit browser
    confirmation and Garmin's own consent. No Garmin activities are downloaded
    or shared with ChatGPT; Garmin push remains disabled.
    """
    from .garmin_link_v101 import connect_link_from_context
    return connect_link_from_context(ctx)


@staging_mcp.tool()
def get_garmin_connection_status(ctx: Context) -> dict:
    """Check Garmin account-link status only; never reveal userId or tokens.

    Connection does not mean real Garmin data can be read here.
    """
    from .garmin_link_v101 import status_from_context
    return status_from_context(ctx)


@staging_mcp.tool()
async def disconnect_garmin_account(confirmation: str, ctx: Context) -> dict:
    """Revoke this user's linked Garmin authorization and delete local Garmin data.

    Mutating operation: the user must explicitly request disconnection and
    provide the literal confirmation DISCONNECT_GARMIN. Requires authenticated
    Neon subject. Does NOT affect fictional demo training activities.
    """
    from .garmin_link_v101 import disconnect_from_context
    return await disconnect_from_context(ctx, confirmation)
