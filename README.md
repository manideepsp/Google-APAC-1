# Google-APAC-1

## Run Entire App With One Command

Start all required services in one terminal (YouTube gRPC, Sheets gRPC, and FastAPI UI/API):

```powershell
poetry run python -m app.startup
```

After startup:

- UI: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/health

Press `Ctrl+C` in that same terminal to stop everything together.

## MCP Server (6 Tools)

A dedicated MCP server is available at `app/mcp_server/server.py`.

Run with stdio transport:

```powershell
$env:MCP_TRANSPORT='stdio'
poetry run python -m app.mcp_server.server
```

Optional transports supported by the server runtime:

- `sse`
- `streamable-http`

Tool mapping:

1. `tool_youtube_data`: YouTube trending data (via existing gRPC YouTube service client)
2. `tool_youtube_analytics`: channel analytics (via existing gRPC YouTube service client)
3. `tool_web_search`: Tavily web search
4. `tool_sqlite_read`: user-scoped active task read from SQLite
5. `tool_sqlite_update`: user-scoped task lifecycle update in SQLite
6. `tool_sheets_sync`: SQLite-to-Sheets sync (via existing gRPC Sheets service client)

## Google ADK Ops Agent

An ADK-based operations agent wrapper is available at `app/adk/ops_agent.py`.
It reuses the same six operational tools via ADK `FunctionTool` bindings.

App-level integration endpoint (authenticated):

- `GET /ops/adk/agent` returns agent name, model, and registered tool count.

Quick smoke test:

```powershell
poetry run python -c "from app.adk.ops_agent import build_ops_agent; a=build_ops_agent(); print(a.name)"
```

## ADK Migration Status

Core workflow agents execute with Google ADK across the end-to-end goal flow:

1. research agent: ADK synthesis for strategy insights
2. planning agent: ADK JSON task generation
3. execution agent: ADK tool-calling for task persistence + sheets sync
4. reflection agent: ADK JSON task regeneration

If ADK execution fails, the API now returns an explicit ADK error response so failures are visible immediately.

`/goal` now runs ADK workflow execution by default.

## AlloyDB AI Feasibility (Current Architecture)

AlloyDB AI is feasible, but should be a phased migration rather than a direct replacement of the current SQLite + Sheets flow.

- Good fit when task/history volume and concurrent users increase significantly.
- Recommended target use: long-term analytics, semantic search over task/research history, and SQL + vector hybrid retrieval.
- Migration complexity: medium.
- Immediate blockers: networked DB operations, schema migration scripts, connection pooling, IAM/service identity setup, and cost baseline.

Suggested path:

1. Keep SQLite as source of truth for active execution loop.
2. Replicate finalized task/research artifacts into AlloyDB AI for analytics/RAG.
3. Move selected read-heavy endpoints to AlloyDB AI.
4. Retire SQLite only after operational parity and cost/performance validation.
