import os
from typing import Literal, cast

from mcp.server.fastmcp import FastMCP

from app.db.sqlite import init_db
from app.mcp_server.tools.sheets_sync_tool import sheets_sync_tool
from app.mcp_server.tools.sqlite_read_tool import sqlite_read_tool
from app.mcp_server.tools.sqlite_update_tool import sqlite_update_tool
from app.mcp_server.tools.web_search_tool import web_search_tool
from app.mcp_server.tools.youtube_analytics_tool import youtube_analytics_tool
from app.mcp_server.tools.youtube_data_tool import youtube_data_tool

init_db()

mcp = FastMCP("google-apac-tools-mcp")


@mcp.tool()
def tool_youtube_data() -> dict:
    """Tool 1/6: Fetch YouTube trending data via gRPC YouTube service."""
    return youtube_data_tool()


@mcp.tool()
def tool_youtube_analytics(channel_id: str) -> dict:
    """Tool 2/6: Fetch channel analytics via gRPC YouTube service."""
    return youtube_analytics_tool(channel_id)


@mcp.tool()
def tool_web_search(query: str, max_results: int = 3) -> dict:
    """Tool 3/6: Run Tavily web search."""
    return web_search_tool(query=query, max_results=max_results)


@mcp.tool()
def tool_sqlite_read(user_id: str) -> dict:
    """Tool 4/6: Read active user tasks from SQLite."""
    return sqlite_read_tool(user_id=user_id)


@mcp.tool()
def tool_sqlite_update(
    user_id: str,
    task_uuid: str,
    status: str | None = None,
    live: bool | None = None,
) -> dict:
    """Tool 5/6: Update a user task status/live lifecycle in SQLite."""
    return sqlite_update_tool(user_id=user_id, task_uuid=task_uuid, status=status, live=live)


@mcp.tool()
def tool_sheets_sync(user_id: str) -> dict:
    """Tool 6/6: Sync a user's active SQLite tasks to Sheets via gRPC client."""
    return sheets_sync_tool(user_id=user_id)


if __name__ == "__main__":
    transport: Literal["stdio", "sse", "streamable-http"]
    env_transport = os.getenv("MCP_TRANSPORT", "stdio")
    if env_transport in {"stdio", "sse", "streamable-http"}:
        transport = cast(Literal["stdio", "sse", "streamable-http"], env_transport)
    else:
        transport = "stdio"
    mcp.run(transport=transport)
