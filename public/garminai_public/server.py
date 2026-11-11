"""GarminAI Public v0.1: demo MCP server. Do NOT expose publicly without auth."""
from mcp.server.fastmcp import FastMCP
from . import core

mcp = FastMCP('GarminAI Public Demo', json_response=True)

@mcp.tool()
def get_sync_status() -> dict:
    """Return DEMO_ONLY status. Garmin accounts are NOT connected."""
    return core.status()

@mcp.tool()
def get_activities(start_date: str = '', end_date: str = '', sport: str = '', limit: int = 50) -> dict:
    """List fictional demo activities; dates ISO YYYY-MM-DD; never real user data."""
    return core.activities(start_date or None,end_date or None,sport or None,limit)

@mcp.tool()
def get_activity_details(activity_id: str) -> dict:
    """Return laps and heart-rate info for one fictional demo activity."""
    return core.detail(activity_id)

@mcp.tool()
def get_training_summary(start_date: str = '',end_date: str = '') -> dict:
    """Summarize fictional running kilometers by ISO week."""
    return core.weekly_summary(start_date or None,end_date or None)

@mcp.tool()
def search_training_literature(topic: str = '',limit: int = 10) -> dict:
    """Search human-reviewed bibliographic sources by topic (intensity, strength, injury, load, etc.)."""
    return core.literature(topic or None,limit)

@mcp.tool()
def get_distance_guidance(distance: str = '10k',language: str = 'sr') -> dict:
    """Get evidence-aware high-level training themes for 5k, 10k, 21k, marathon. Not a prescription."""
    return core.guidance(distance,language)

if __name__ == '__main__':
    mcp.run(transport='streamable-http')
