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


@staging_mcp.tool()
def run_synthetic_push_rehearsal(confirmation: str, ctx: Context) -> dict:
    """Explicitly test Neon push inbox with ONE synthetic activity (no Garmin API calls).

    Requires the exact confirmation RUN_SYNTHETIC_REHEARSAL and operator opt-in
    GARMINAI_PUSH_REHEARSAL_STAGING_ENABLED=1. Saves at most one marked fictional
    inbox row for the verified Neon user and proves a repeated insert is ignored.
    No real Garmin workouts, tokens, AI sharing, or public push ingress.
    """
    from .garmin_push_e2e_v112 import rehearse_from_context
    return rehearse_from_context(ctx, confirmation)


@staging_mcp.tool()
def run_synthetic_edge_to_neon_rehearsal(confirmation: str, ctx: Context) -> dict:
    """Explicitly move ONE fictional receipt Cloudflare D1 -> Neon via the caller's verified subject.

    Requires RUN_SYNTHETIC_EDGE_TO_NEON and the operator-staged bridge secret +
    GARMINAI_EDGE_BRIDGE_STAGING_ENABLED=1. D1 receipt is ACKed only after
    Neon durable commit. Retry is idempotent. No real Garmin activities,
    public Render webhook, Garmin push or AI data sharing.
    """
    from .garmin_edge_to_neon_v117 import deliver_from_context
    return deliver_from_context(ctx,confirmation)


@staging_mcp.tool()
def run_synthetic_delivery_recovery(confirmation: str, scenario: str, ctx: Context) -> dict:
    """Operator-confirmed FICTIONAL D1->Neon failure/recovery scenario (v1.1.8).

    Confirmation: RUN_SYNTHETIC_DELIVERY_RECOVERY; operator must separately
    set GARMINAI_EDGE_RECOVERY_STAGING_ENABLED=1. Allowed scenario values:
    SIMULATE_RENDER_DELAY, SIMULATE_NEON_UNAVAILABLE,
    SIMULATE_D1_ACK_UNAVAILABLE, RECOVER. No actual service outage is induced.
    Neon writes only in ACK-omission and RECOVER modes; one fixed synthetic
    event per verified subject. Never reads real Garmin activities or opens
    Garmin ingress, and does not schedule background retries.
    """
    from .garmin_delivery_recovery_v118 import rehearse_from_context
    return rehearse_from_context(ctx, confirmation, scenario)


@staging_mcp.tool()
def get_synthetic_delivery_recovery_status(ctx: Context) -> dict:
    """READ ONLY caller-scoped state of fictional D1 recovery receipt.

    Returns only pending/acknowledged and count of claim attempts, never
    account identifiers, activity contents, Garmin data, or service secrets.
    Does not independently audit Neon and is not production readiness.
    """
    from .garmin_delivery_recovery_v118 import status_from_context
    return status_from_context(ctx)
