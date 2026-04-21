# 🚀 Google-APAC-1 — AI YouTube Strategy Console

An AI strategy console that turns a creator’s goal into a **practical, trackable, and improvable execution workflow**.

It combines:
- 🤖 **Google ADK agents** for research/planning/execution/reflection
- 🧰 **Operational tools** exposed through an MCP server
- 🗂️ **SQLite** for active task operations and product state
- 🧠 **AlloyDB (PostgreSQL)** for generation memory and relevance retrieval
- 📊 **Google Sheets sync** for operational visibility
- 🎬 **YouTube + Web intelligence** for strategy decisions

---

## 🎯 1) Project Goal

Convert a creator’s high-level YouTube goal into:
1. **Goal parameters** (Goal, Audience, Budget, Timeline, Content Type, Channel ID)
2. **Research-backed strategic insights**
3. **Actionable task plans** (priority + day)
4. **Executable task state** (TODO / IN_PROGRESS / COMPLETED / OUT_OF_SCOPE)
5. **Continuous improvement loop** via reflection and KPI feedback

---

## ✨ 2) Key Features (Hierarchical)

### 2.1 User & Workspace
- 🔐 Email/password auth with session tokens
- 🧾 Forgot/reset password flow
- 📺 Channel ID parsing and channel-scoped workspaces

### 2.2 Goal Building
- 💬 Chat-assisted goal drafting (`/goal/assistant`)
- 🧩 Editable goal parameter table in UI
- ✅ Readiness gating before generation

### 2.3 AI Strategy Workflow
- 🔎 Research agent gathers trends, channel analytics, and web insights
- 🧠 Planning agent generates tasks from goal + research + memory
- ⚙️ Execution agent persists tasks and syncs Sheets
- 🔁 Reflection agent re-generates tasks from performance signals

### 2.4 Task Operations
- 📝 Update task fields (priority/status/live)
- 📦 Move between active tasks and archive
- 🕓 Modification trace/history

### 2.5 Analytics & Insights UI
- 📈 KPI cards (avg/max views, trends, keywords)
- 📚 Run history and archived runs
- 💡 Ideas panel from web insights

### 2.6 Tooling Surfaces
- 🔌 MCP server with 6 tools
- 🛠️ ADK Ops Agent wrapping the same 6 tools

---

## 🧱 3) Architecture Overview

```mermaid
flowchart TD
    U[👤 User] --> UI[🖥️ FastAPI-served UI]
    UI --> API[⚡ FastAPI API Router]

    API --> GW[🤖 ADK Workflow Runner]
    GW --> RA[Research Agent]
    GW --> PA[Planning Agent]
    GW --> EA[Execution Agent]
    API --> RF[Reflection Agent]

    RA --> YT[🎬 YouTube gRPC Service]
    RA --> WS[🌐 Tavily Web Search]
    RA --> KP[📊 KPI Builder]

    PA --> ALR[🧠 AlloyDB Related Memory Fetch]
    PA --> ADK1[Gemini via Vertex AI]
    PA --> ALW[🧠 AlloyDB Generation Memory Write]

    EA --> SQ[🗂️ SQLite Tasks]
    EA --> SS[📊 Sheets Sync Service]
    RF --> SQ
    RF --> YT
    RF --> ADK2[Gemini via Vertex AI]
    RF --> ALW

    API --> SQ
    API --> ALR
    API --> UI
```

---

## 🤖 4) Agents Included and Role of Each

### 4.1 Workflow Agents (`app/agents/*`)
1. **Research Agent** (`research_agent.py`)
   - Pulls trending titles/topics from YouTube gRPC
   - Fetches multi-channel analytics
   - Runs goal-driven web search
   - Builds KPI payload and creates ADK research summary

2. **Planning Agent** (`planning_agent.py`)
   - Fetches related prior tasks from AlloyDB
   - Calls ADK to generate JSON tasks
   - Stores generation memory back to AlloyDB

3. **Execution Agent** (`execution_agent.py`)
   - Persists generated tasks into SQLite
   - Triggers SQLite → Sheets sync

4. **Reflection Agent** (`reflection_agent.py`)
   - Reads current performance/task context
   - Re-generates improved tasks using ADK
   - Replaces active tasks, syncs Sheets, records memory in AlloyDB

### 4.2 Operations Agent
5. **ADK Ops Agent** (`app/adk/ops_agent.py`)
   - Operational agent bound to the same 6 MCP-aligned tools
   - Exposed via `/ops/adk/agent` for metadata/verification

---

## 🧰 5) Tools Included and Role of Each

MCP server (`app/mcp_server/server.py`) exposes **6 tools**:

1. `tool_youtube_data` → trending titles/topics
2. `tool_youtube_analytics(channel_id)` → channel growth + top videos
3. `tool_web_search(query, max_results)` → Tavily web intelligence
4. `tool_sqlite_read(user_id)` → user active tasks from SQLite
5. `tool_sqlite_update(user_id, task_uuid, status, live)` → task lifecycle update
6. `tool_sheets_sync(user_id)` → sync user tasks to Google Sheets

---

## 🔗 6) How Agents and Tools Are Connected

```mermaid
flowchart LR
    subgraph Agents
      RA[Research]
      PA[Planning]
      EA[Execution]
      RF[Reflection]
      OA[Ops Agent]
    end

    subgraph Tools
      T1[YouTube Data]
      T2[YouTube Analytics]
      T3[Web Search]
      T4[SQLite Read]
      T5[SQLite Update]
      T6[Sheets Sync]
    end

    RA --> T1
    RA --> T2
    RA --> T3

    EA --> T4
    EA --> T6

    RF --> T2
    RF --> T4
    RF --> T6

    OA --> T1
    OA --> T2
    OA --> T3
    OA --> T4
    OA --> T5
    OA --> T6

    PA --> AL[AlloyDB Memory Fetch/Write]
```

---

## 🗃️ 7) Database Design: AlloyDB + Other DBs

### 7.1 SQLite (Operational Source of Truth)
Used for:
- users, sessions, password resets
- active tasks and archived task history
- strategy runs and research snapshots
- task modification logs

Why:
- fast local operations
- simple deployment footprint
- channel/user scoped task lifecycle operations

### 7.2 AlloyDB (Generation Memory Layer)
Used for:
- storing generation task memory (`generation_task_memory`)
- relevance search for related historical tasks
- FTS + trigram + recency scoring for retrieval

How it helps:
- continuity across generations
- duplicate reduction
- better context-aware planning/reflection

### 7.3 Google Sheets (Operational Mirror)
Used for:
- mirrored view of active tasks
- simple external visibility/reporting

---

## ⚙️ 8) Local Setup Instructions

### 8.1 Prerequisites
- Python **3.11+**
- Poetry
- Google Cloud credentials (ADC or service-account JSON)
- API keys as needed (YouTube Data API, Tavily)

### 8.2 Install
```bash
cd /home/runner/work/Google-APAC-1/Google-APAC-1
poetry install
```

### 8.3 Configure environment
Set minimum required variables:

```bash
# Vertex / Gemini via Vertex AI
export GOOGLE_CLOUD_PROJECT="<your-project-id>"
export GOOGLE_CLOUD_LOCATION="us-central1"

# Optional alias names supported by app
export VERTEX_PROJECT_ID="<your-project-id>"
export VERTEX_LOCATION="us-central1"

# Optional, if using service-account file directly
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/credentials.json"

# Required for YouTube fetches
export YOUTUBE_API_KEY="<your-youtube-api-key>"

# Required for web search
export TAVILY_API_KEY="<your-tavily-api-key>"

# Optional AlloyDB memory
export ALLOYDB_DSN="postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
# or
export ALLOYDB_URI="postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"

# Optional gRPC ports/hosts
export YOUTUBE_GRPC_HOST="localhost"
export YOUTUBE_GRPC_PORT="50051"
export SHEETS_GRPC_HOST="localhost"
export SHEETS_GRPC_PORT="50052"
```

Authenticate ADC if needed:
```bash
gcloud auth application-default login
```

### 8.4 Run full app stack
```bash
poetry run python -m app.startup
```
This starts:
- YouTube gRPC service
- Sheets gRPC service
- FastAPI UI/API server

Access:
- UI: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`

---

## 🧪 9) Usage Flow (End-to-End)

1. Register/Login from UI
2. Add/parse Channel ID
3. Build goal params through chat assistant
4. Generate strategy (`/goal`)
5. Review tasks in Workspace
6. Edit/move tasks (trace logged)
7. Run Analyze (`/analyze`) for reflection-driven updates
8. Review Ideas/Analytics/Archive tabs

---

## 🌐 10) API Highlights

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /goal/assistant`
- `POST /goal`
- `POST /analyze`
- `POST /task/update`
- `POST /task/move`
- `GET /tasks`
- `GET /tasks/history`
- `GET /tasks/modifications`
- `GET /runs`
- `GET /archive`
- `GET /research/latest`
- `GET /ops/adk/agent`

---

## 🛰️ 11) MCP Server Usage

Run MCP server:
```bash
export MCP_TRANSPORT=stdio
poetry run python -m app.mcp_server.server
```

Supported transports:
- `stdio`
- `sse`
- `streamable-http`

---

## 🔁 12) CI/CD Pipeline to Google Cloud Run

> The deployment architecture is designed as **GitHub Repo → Cloud Build Trigger → Artifact Registry → Cloud Run**.

```mermaid
flowchart LR
    GH[📦 GitHub Repository] --> TR[⚡ Cloud Build Trigger]
    TR --> CB[🏗️ Cloud Build]
    CB --> AR[📚 Artifact Registry]
    AR --> CR[☁️ Cloud Run Service]
    CR --> U[👤 Users]
```

### Pipeline intent
1. Push/merge to configured branch in GitHub
2. Cloud Build trigger starts build
3. Docker image built from repo `Dockerfile`
4. Image pushed to Artifact Registry
5. Cloud Run deploys new revision
6. Traffic routed to latest healthy revision

---

## 📁 13) Important Paths

- `app/main.py` — FastAPI app entry
- `app/startup.py` — launches all runtime services
- `app/api/routes.py` — HTTP API contract
- `app/agents/*` — workflow agents
- `app/adk/*` — ADK workflow + ops agent
- `app/mcp_server/*` — MCP server and tools
- `app/db/sqlite.py` — SQLite operational persistence
- `app/db/alloydb.py` — AlloyDB memory and retrieval
- `app/services/*` — YouTube/Sheets/web integrations
- `ui/*` — frontend application
- `Dockerfile` — container runtime for Cloud Run

---

## ✅ 14) What This Repository Demonstrates

- Full-stack AI strategy product pattern
- Agentic orchestration with ADK
- Tool-first operations via MCP
- Hybrid data strategy: operational DB + memory DB
- Practical deployment path from GitHub to Cloud Run
