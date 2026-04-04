from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from app.mcp_server.tools.sheets_sync_tool import sheets_sync_tool
from app.mcp_server.tools.sqlite_read_tool import sqlite_read_tool
from app.mcp_server.tools.sqlite_update_tool import sqlite_update_tool
from app.mcp_server.tools.web_search_tool import web_search_tool
from app.mcp_server.tools.youtube_analytics_tool import youtube_analytics_tool
from app.mcp_server.tools.youtube_data_tool import youtube_data_tool


def build_ops_agent(model: str = "gemini-2.5-flash") -> Agent:
    """Build a Google ADK agent wired to the same six operational tools."""
    return Agent(
        name="strategy_ops_agent",
        model=model,
        instruction=(
            "You are an operations agent for YouTube strategy workflows. "
            "Use tools for trend retrieval, analytics, web research, user-scoped task reads/updates, and sheets sync."
        ),
        tools=[
            FunctionTool(youtube_data_tool),
            FunctionTool(youtube_analytics_tool),
            FunctionTool(web_search_tool),
            FunctionTool(sqlite_read_tool),
            FunctionTool(sqlite_update_tool),
            FunctionTool(sheets_sync_tool),
        ],
    )
