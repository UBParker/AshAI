# AshAI Developer Onboarding

Welcome to AshAI — an open-source, provider-agnostic AI coding assistant with multi-agent coordination, shared project workspaces, and a gateway architecture that spawns isolated per-user backend instances.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Project Structure](#project-structure)
4. [Backend Deep Dive](#backend-deep-dive)
5. [Frontend Deep Dive](#frontend-deep-dive)
6. [Gateway & Deployment](#gateway--deployment)
7. [Agent System](#agent-system)
8. [Database](#database)
9. [Adding New Features](#adding-new-features)
10. [Environment & Config](#environment--config)
11. [Testing](#testing)
12. [Deployment](#deployment)
13. [Common Workflows](#common-workflows)

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- An LLM API key (Anthropic, OpenAI, or a local Ollama instance)

### Local Development

```bash
# 1. Clone and install backend
git clone <repo-url>
cd helperAI
pip install -e ".[dev]"

# 2. Create your .env (copy from example, add your API key)
cp .env.example .env
# Edit .env — set at least one provider key:
#   HELPERAI_ANTHROPIC_API_KEY=sk-ant-...
#   or HELPERAI_OPENAI_API_KEY=sk-...
#   or HELPERAI_OLLAMA_BASE_URL=http://localhost:11434

# 3. Run the backend
make run
# Backend is now at http://localhost:8000

# 4. In a separate terminal, run the frontend
cd src/frontend
npm install
npm run dev
# Frontend is now at http://localhost:5173
```

You should see the AshAI chat interface. Type a message — Eve (the master agent) will respond.

### Makefile Shortcuts

```
make install          # pip install -e .
make dev              # pip install -e ".[dev]"
make run              # python3 -m helperai
make test             # pytest tests/ -v
make lint             # ruff check
make fmt              # ruff format + fix
make frontend-install # npm install in src/frontend
make frontend-dev     # npm run dev
make frontend-build   # npm run build
make clean            # remove cache/artifacts
```

---

## Architecture Overview

AshAI runs in three modes:

### 1. Local Dev Mode (no auth)
```
Browser (localhost:5173) → SvelteKit dev server
    ↓ /api/* calls
Backend (localhost:8000) → FastAPI + agents + SQLite
```

### 2. Desktop Mode (Tauri)
```
Tauri window → loads built SvelteKit SPA
    ↓ spawns
Python sidecar (desktop_main.py) → FastAPI on random port
    ↓ stores data in
~/.ashai/ (macOS) or %APPDATA%/ashai (Windows)
```

### 3. Production Web Mode (Fly.io)
```
Browser (app.ashai.net)
    ↓ all requests
Gateway (port 9000) ── serves static frontend
    │                ── validates Supabase JWTs
    │                ── reverse proxies /api/* requests
    ↓ spawns per-user subprocesses
Backend Instance (port 10001) ← User A's isolated instance
Backend Instance (port 10002) ← User B's isolated instance
Backend Instance (port 10003) ← Shared project instance
    ↓
SQLite per instance at /data/users/{id}/ or /data/projects/{id}/
```

### Key Insight

The gateway is a **reverse proxy + process manager**. The browser never connects directly to backend instances. All `/api/*` requests go through the gateway, which extracts the JWT, looks up the user's running instance, and forwards the request.

---

## Project Structure

```
helperAI/
├── src/
│   ├── helperai/                    # Python backend
│   │   ├── __main__.py              # Entry point: python -m helperai
│   │   ├── desktop_main.py          # Tauri/desktop entry point
│   │   ├── gateway.py               # Production gateway (Fly.io)
│   │   ├── config.py                # Pydantic settings (reads .env)
│   │   ├── api/
│   │   │   ├── app.py               # FastAPI app factory + lifespan
│   │   │   ├── deps.py              # Dependency injection globals
│   │   │   └── routes/
│   │   │       ├── chat.py          # POST /api/chat (SSE streaming)
│   │   │       ├── agents.py        # CRUD + message agents
│   │   │       ├── ws.py            # WebSocket real-time events
│   │   │       ├── approvals.py     # Tool approval workflow
│   │   │       ├── knowledge.py     # Knowledge base CRUD
│   │   │       ├── providers.py     # List LLM providers/models
│   │   │       ├── tools.py         # List available tools
│   │   │       └── settings.py      # Read/write .env config
│   │   ├── agents/
│   │   │   ├── manager.py           # AgentManager — lifecycle + queuing
│   │   │   ├── agent.py             # ConversationalAgent — run loop
│   │   │   ├── eve.py               # Eve/Ash system prompt
│   │   │   └── state.py             # Agent state machine
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy ORM models
│   │   │   └── engine.py            # Async DB setup
│   │   ├── llm/
│   │   │   ├── protocol.py          # LLMProvider interface
│   │   │   ├── message_types.py     # Message, ToolCall, StreamChunk
│   │   │   ├── anthropic_provider.py # Anthropic SDK integration
│   │   │   ├── openai_compat.py     # OpenAI-compatible (+ Ollama)
│   │   │   └── registry.py          # Provider name → instance map
│   │   ├── core/
│   │   │   ├── events.py            # In-process pub/sub EventBus
│   │   │   └── approval.py          # Tool approval (pause/resume)
│   │   ├── tools/
│   │   │   ├── protocol.py          # Tool interface + ToolContext
│   │   │   ├── registry.py          # Tool name → instance map
│   │   │   └── builtin/             # spawn_agent, list_agents, etc.
│   │   └── plugins/
│   │       ├── protocol.py          # Plugin interface
│   │       └── loader.py            # Auto-discovery from disk
│   └── frontend/                    # SvelteKit SPA
│       ├── src/
│       │   ├── routes/
│       │   │   ├── +layout.svelte   # Root layout (auth, WS, sidebar)
│       │   │   ├── +page.svelte     # Home chat (Eve)
│       │   │   ├── login/           # Auth page
│       │   │   ├── setup/           # Onboarding (API keys)
│       │   │   ├── agents/[id]/     # Agent-specific chat
│       │   │   ├── friends/         # Friend management
│       │   │   ├── projects/        # Project management
│       │   │   └── invite/[code]/   # Accept invites
│       │   └── lib/
│       │       ├── api/client.js    # API client (fetch + SSE + WS)
│       │       ├── auth.js          # Supabase auth wrapper
│       │       ├── config.js        # Build-time env vars
│       │       ├── stores/          # Svelte stores (chat, agents, etc.)
│       │       └── components/      # UI components
│       ├── svelte.config.js
│       ├── vite.config.js
│       └── package.json
├── plugins/                         # Built-in plugins
│   ├── claude_code/                 # Claude CLI integration
│   ├── system_tools/                # File/shell/browser tools
│   ├── computer_use/                # Screen control tools
│   └── example_plugin/              # Template for new plugins
├── tests/                           # pytest tests
├── src-tauri/                       # Tauri desktop wrapper
├── supabase/                        # DB migrations
├── Dockerfile                       # Multi-stage build
├── fly.toml                         # Fly.io config
├── pyproject.toml                   # Python project config
└── Makefile
```

---

## Backend Deep Dive

### App Startup Flow (`api/app.py`)

When the backend starts, the lifespan function runs:

1. **Initialize database** — Creates SQLAlchemy async engine, runs `CREATE TABLE IF NOT EXISTS`
2. **Create EventBus** — In-process pub/sub for real-time events
3. **Register LLM providers** — Checks which API keys exist, registers Ollama/OpenAI/Anthropic
4. **Register builtin tools** — `spawn_agent`, `list_agents`, `message_agent`, `report_to_eve`
5. **Load plugins** — Scans `plugins/` directory, each plugin registers its tools
6. **Initialize ApprovalManager** — Handles tool approval pause/resume
7. **Initialize AgentManager + Eve** — Creates the master agent (Ash/Eve)
8. **Store in deps** — All singletons go into `api/deps.py` for dependency injection

### Request Flow: Sending a Chat Message

```
POST /api/chat {"message": "Hello", "agent_id": null}
    ↓
routes/chat.py → ChatRequest parsed
    ↓
AgentManager.send_message_stream(eve_id, "Hello")
    ↓
ConversationalAgent.step_stream():
    1. agent.add_user_message("Hello")
    2. Query LLM (Anthropic/OpenAI) with conversation history + tools
    3. LLM returns text + optional tool_calls
    4. If tool_calls:
       a. Check approval requirement
       b. Execute tool (might spawn sub-agent, run code, etc.)
       c. Append tool result to conversation
       d. Go back to step 2 (re-query LLM with results)
    5. Yield SSE events: content chunks, tool_call, tool_result, done
    ↓
StreamingResponse (text/event-stream) → client
```

### LLM Providers

All providers implement the `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    name: str
    async def stream(self, messages, tools, model) -> AsyncIterator[StreamChunk]: ...
    async def list_models(self) -> list[str]: ...
```

- **Anthropic** (`llm/anthropic_provider.py`): Uses official SDK, handles system prompt extraction
- **OpenAI-compatible** (`llm/openai_compat.py`): Works with OpenAI, Ollama, vLLM, LM Studio

### Event System (`core/events.py`)

Real-time updates use an in-process EventBus:

```python
# Event types
AGENT_CREATED, AGENT_STATUS_CHANGED, AGENT_MESSAGE,
AGENT_STREAM_CHUNK, AGENT_STREAM_END,
APPROVAL_REQUESTED, APPROVAL_RESOLVED
```

The WebSocket route (`routes/ws.py`) subscribes to all events and relays them to the browser.

### Tool Approval (`core/approval.py`)

Some tools (like `run_command`) require user approval:

1. Agent calls a restricted tool
2. `ApprovalManager.request_approval()` creates a `PendingApproval` in the DB
3. An `asyncio.Future` is created — the agent's coroutine **suspends**
4. `APPROVAL_REQUESTED` event fires → frontend shows a dialog
5. User clicks Approve/Deny → `POST /api/approvals/{id}/approve`
6. `ApprovalManager.resolve()` completes the Future → agent resumes

---

## Frontend Deep Dive

### Tech Stack

- **SvelteKit 2.0** with Svelte 5 (runes syntax: `$state`, `$derived`, `$effect`)
- **Vite** build tool
- **Static adapter** — builds to a pre-rendered SPA (no SSR)
- **Supabase** for auth (optional, only in web mode)

### Key Files

| File | What it does |
|------|-------------|
| `+layout.svelte` | Root layout — handles auth, backend connection, WebSocket setup, sidebar toggle |
| `lib/api/client.js` | All API calls — fetch wrapper with auth headers, SSE streaming, WebSocket |
| `lib/auth.js` | Supabase auth — sign in, sign up, get JWT, session management |
| `lib/stores/chat.js` | Message store — manages conversation state, streaming chunks |
| `lib/stores/agents.js` | Agent list store — refreshes from API, handles WS events |
| `components/ChatPanel.svelte` | Main chat UI — input, messages, SSE event handler |
| `components/MessageBubble.svelte` | Single message rendering — markdown, tool calls |
| `components/AgentSidebar.svelte` | Left sidebar — agent list, nav links |

### Auth Flow (Web Mode)

1. User visits `app.ashai.net` → `+layout.svelte` checks `isAuthEnabled()`
2. If not logged in → redirect to `/login`
3. User signs in via Supabase → gets JWT
4. `+layout.svelte` calls `POST /gateway/session` with JWT
5. Gateway validates JWT, spawns backend instance, returns `{status: "started"}`
6. Frontend calls `waitForBackend()` to poll `/api/health`
7. Frontend opens WebSocket at `/api/ws?token=JWT`
8. App is ready — user can chat

### SSE Streaming (Chat)

```javascript
// In ChatPanel.svelte
const events = chatStream(message, agentId, senderName);
for await (const event of events) {
    switch (event.type) {
        case 'content':    addAssistantChunk(event.text); break;
        case 'tool_call':  addToolCall(event.name, event.arguments, event.id); break;
        case 'tool_result': updateToolResult(event.name, event.content); break;
        case 'done':       finalizeAssistant(); break;
        case 'queued':     showQueuedMessage(event.position); break;
    }
}
```

### Stores (Svelte 5 Runes)

The frontend uses Svelte's `writable` stores for shared state:

- `chat.js` — `messages`, `isStreaming`, `currentAgentId`
- `agents.js` — `agents` list, refreshed from API and WebSocket events
- `approvals.js` — `pendingApprovals`, drives the approval dialog
- `projects.js` — `projects`, `currentProject` (null = personal mode)
- `friends.js` — `friends`, `friendRequests`

---

## Gateway & Deployment

### How the Gateway Works (`gateway.py`)

The gateway is the production entry point. It does four things:

#### 1. Serves the Frontend
Built SvelteKit files are at `/app/static`. The gateway mounts `/_app` for hashed assets and serves `index.html` as a SPA fallback for all other GET routes.

#### 2. Validates Auth
Every `/api/*` and `/gateway/*` request must include `Authorization: Bearer <jwt>`. The gateway calls `supabase.auth.get_user(token)` to validate.

#### 3. Manages Instances
```python
personal_instances: dict[str, Instance]  # keyed by user_id
project_instances: dict[str, Instance]   # keyed by project_id
```

- `POST /gateway/session` — Spawn/find personal instance
- `POST /gateway/project-session` — Spawn/find shared project instance
- Idle reaper runs every 5 min, kills instances idle > 30 min (personal) or 15 min with no users (project)
- Port pool: 10001–10100

#### 4. Reverse Proxies API Calls
```
Browser → GET /api/agents
    ↓
Gateway extracts JWT → looks up user's instance (port 10042)
    ↓
Forwards to http://127.0.0.1:10042/api/agents
    ↓
Returns response to browser
```

SSE streams (chat) and WebSockets are also proxied.

### Instance Isolation

Each user gets their own:
- Backend process (separate PID)
- SQLite database (at `/data/users/{user_id}/ashai.db`)
- Agent state (their own Eve, their own sub-agents)
- Conversation history

Shared projects get:
- One instance per project (at `/data/projects/{project_id}/`)
- Multiple users connect to the same instance
- Messages labeled with `sender_name` so you can see who said what
- Message queuing if two users message simultaneously

---

## Agent System

### Eve (Ash) — The Master Agent

Eve is the main agent users chat with. She can:
- Answer questions directly
- Spawn sub-agents for complex tasks
- Coordinate multiple sub-agents working in parallel
- Receive reports from sub-agents

Her system prompt is defined in `agents/eve.py` and dynamically includes:
- Available tools and their descriptions
- Knowledge base entries (if any exist)

### Sub-Agents

Eve spawns sub-agents using the `spawn_agent` tool:

```
User: "Analyze my codebase and write tests"
Eve: [spawn_agent name="CodeAnalyzer" tools=["claude_code"] goal="Analyze codebase"]
Eve: [spawn_agent name="TestWriter" tools=["run_command"] goal="Write tests"]
```

Sub-agents:
- Have their own conversation thread
- Can use specific tools (assigned at creation)
- Always have `report_to_eve` tool to send results back
- Run independently and concurrently

### Agent State Machine

```
CREATED → IDLE → RUNNING → IDLE (loop)
                    ↓
                  ERROR
                    ↓
               IDLE or DESTROYED
```

Only valid transitions are allowed. The state machine prevents race conditions.

### Builtin Tools

| Tool | Description |
|------|-------------|
| `spawn_agent` | Create a new sub-agent with specific tools and goals |
| `list_agents` | List all active agents and their status |
| `message_agent` | Send a message to a sub-agent and get the response |
| `report_to_eve` | Sub-agent reports findings back to Eve |

### Plugin Tools

Plugins in `plugins/` provide additional tools:

- **claude_code** — Run Claude CLI commands
- **system_tools** — File operations, shell commands, browser control
- **computer_use** — Screen capture, mouse/keyboard control

---

## Database

### ORM Models (`db/models.py`)

```python
Agent          # id, name, role, goal, status, provider, model, tool_names, parent_id
ThreadMessage  # id, agent_id, role, content, tool_calls, sender_name, sequence
PendingApproval # id, agent_id, tool_name, arguments, status
KnowledgeEntry # id, title, content, added_by, created_at
ProviderConfig # id, provider_name, config_json (future use)
```

### Supabase Tables (Production Auth)

These live in Supabase (not in the local SQLite):

```sql
profiles         — id (uuid), email, display_name
friendships      — requester_id, addressee_id, status (pending/accepted/declined)
projects         — id, name, description, owner_id
project_members  — project_id, user_id, role (owner/editor/viewer)
invites          — code, type (friend/project), creator_id, max_uses
```

### Data Storage

- **Local dev**: `./helperai.db` (single SQLite file)
- **Desktop**: `~/.ashai/helperai.db`
- **Production**: `/data/users/{user_id}/ashai.db` per user, `/data/projects/{project_id}/ashai.db` per project

---

## Adding New Features

### Adding a New API Route

1. Create `src/helperai/api/routes/myfeature.py`:
   ```python
   from fastapi import APIRouter
   router = APIRouter(prefix="/api/myfeature", tags=["myfeature"])

   @router.get("/")
   async def list_items():
       return {"items": []}
   ```

2. Register in `src/helperai/api/app.py`:
   ```python
   from helperai.api.routes import myfeature
   app.include_router(myfeature.router)
   ```

### Adding a New Tool (Plugin)

1. Create `plugins/my_tool/__init__.py`:
   ```python
   from helperai.plugins.protocol import PluginProtocol
   from helperai.tools.protocol import Tool, ToolContext
   from helperai.llm.message_types import ToolDefinition

   class MyTool:
       @property
       def definition(self) -> ToolDefinition:
           return ToolDefinition(
               name="my_tool",
               description="Does something useful",
               parameters={"type": "object", "properties": {...}},
           )

       async def execute(self, arguments: dict, context: ToolContext) -> str:
           return "result"

   class MyPlugin:
       name = "my_tool"
       description = "My custom tool"
       def register_tools(self, registry):
           registry.register(MyTool())

   plugin = MyPlugin()
   ```

The plugin loader auto-discovers it on startup.

### Adding a New LLM Provider

1. Implement the `LLMProvider` protocol in `src/helperai/llm/my_provider.py`
2. Register in `api/app.py` startup alongside the existing providers

### Adding a Frontend Page

1. Create `src/frontend/src/routes/mypage/+page.svelte`
2. SvelteKit auto-routes it to `/mypage`
3. Use `apiFetch()` from `lib/api/client.js` for API calls

---

## Environment & Config

### Backend Config (`config.py`)

All settings use the `HELPERAI_` prefix and are loaded from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HELPERAI_PORT` | 8000 | Backend port |
| `HELPERAI_HOST` | 127.0.0.1 | Backend host |
| `HELPERAI_LOG_LEVEL` | info | Logging level |
| `HELPERAI_DEFAULT_PROVIDER` | ollama | Default LLM provider |
| `HELPERAI_ANTHROPIC_API_KEY` | — | Anthropic API key |
| `HELPERAI_OPENAI_API_KEY` | — | OpenAI API key |
| `HELPERAI_OLLAMA_BASE_URL` | http://localhost:11434 | Ollama server URL |
| `HELPERAI_DATABASE_URL` | sqlite+aiosqlite:///./helperai.db | Database connection |
| `HELPERAI_DATA_DIR` | — | Override data directory |
| `HELPERAI_INSTANCE_TYPE` | personal | Set by gateway (personal/project) |

### Frontend Config

Build-time env vars (set in Dockerfile or `.env`):

| Variable | Description |
|----------|-------------|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon (public) key |
| `VITE_GATEWAY_URL` | Gateway URL (empty = same origin) |

### Gateway Config (Production)

Set as Fly.io secrets or env vars:

| Variable | Description |
|----------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (secret) |
| `GATEWAY_PORT` | 9000 |
| `GATEWAY_DATA_DIR` | /data |
| `HELPERAI_ANTHROPIC_API_KEY` | Passed to spawned instances |

---

## Testing

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_event_bus.py -v

# Run with coverage
pytest tests/ --cov=helperai
```

### Test Structure

```
tests/
├── conftest.py                  # Shared fixtures
├── unit/
│   ├── test_event_bus.py        # EventBus pub/sub
│   ├── test_state_machine.py    # Agent state transitions
│   ├── test_llm_registry.py     # Provider registration
│   ├── test_tool_registry.py    # Tool registration
│   ├── test_config.py           # Settings loading
│   └── test_message_types.py    # Message serialization
└── integration/
    ├── test_api.py              # Full API request flows
    └── test_agent_lifecycle.py  # Agent create → chat → destroy
```

### Key Test Fixtures (`conftest.py`)

- `settings` — Test config with in-memory SQLite
- `event_bus` — Fresh EventBus per test
- `llm_registry` / `tool_registry` — Empty registries

---

## Deployment

### Production Stack

| Component | Platform | URL |
|-----------|----------|-----|
| Gateway + Frontend | Fly.io | app.ashai.net |
| Auth + User DB | Supabase | mjosrqijnvjtkywadbxm.supabase.co |
| DNS | Squarespace | ashai.net |
| TLS | Fly.io (Let's Encrypt) | auto-managed |

### Deploy Commands

```bash
# Set a secret
~/.fly/bin/fly secrets set HELPERAI_ANTHROPIC_API_KEY="sk-ant-..."

# Deploy (with cache busting if needed)
~/.fly/bin/fly deploy --no-cache

# Check logs
~/.fly/bin/fly logs

# SSH into running container
~/.fly/bin/fly ssh console

# Check health
curl https://app.ashai.net/gateway/health
```

### Dockerfile (Multi-Stage)

```
Stage 1 (node:20-slim):
  - Installs frontend deps
  - Builds SvelteKit SPA with baked-in env vars
  - Output: /app/src/frontend/build

Stage 2 (python:3.12-slim):
  - Installs Python deps with [gateway] extras
  - Copies built frontend to /app/static
  - Creates /data directory for instance databases
  - Runs: python -m helperai.gateway
```

### fly.toml Key Settings

- **Region**: `iad` (US East)
- **VM**: `shared-cpu-2x`, 1024 MB RAM
- **Volume**: `ashai_data` mounted at `/data` (persistent across deploys)
- **Ports**: 80/443 → internal 9000
- **Health check**: `GET /gateway/health`
- **Auto-stop**: disabled (always running)

---

## Common Workflows

### "I want to change how agents respond"

1. Look at `agents/eve.py` for the system prompt
2. Look at `agents/agent.py` → `step_stream()` for the run loop
3. Look at `agents/manager.py` → `send_message_stream()` for the entry point

### "I want to add a new tool for agents"

1. Create a plugin in `plugins/my_tool/`
2. Or add a builtin in `tools/builtin/`
3. Register it — plugins auto-register, builtins go in `api/app.py`

### "I want to change the chat UI"

1. `components/ChatPanel.svelte` — the main chat panel
2. `components/MessageBubble.svelte` — individual messages
3. `stores/chat.js` — message state management
4. `lib/api/client.js` → `chatStream()` — SSE connection

### "I want to debug a production issue"

```bash
# Check health
curl https://app.ashai.net/gateway/health

# View logs
~/.fly/bin/fly logs

# SSH in and inspect
~/.fly/bin/fly ssh console
ls /data/users/
cat /data/users/<user_id>/ashai.db  # (it's SQLite)

# Check running processes
ps aux | grep helperai
```

### "I want to test auth locally"

Set these in your `.env`:
```
HELPERAI_AUTH_ENABLED=true
```

And in `src/frontend/.env`:
```
VITE_SUPABASE_URL=https://mjosrqijnvjtkywadbxm.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key>
```

Then run both backend and frontend. You'll be redirected to the login page.

---

## Important Patterns

### Dependency Injection
All global services are stored in `api/deps.py` and accessed via FastAPI's `Depends()`. This makes testing easy — swap in mocks.

### Async Everything
The backend is fully async: async SQLAlchemy sessions, async HTTP clients, async tool execution, `asyncio.Queue` for message queuing, `asyncio.Future` for approval pausing.

### Event-Driven UI
Agent events flow: `AgentManager` → `EventBus` → `WebSocket route` → `Browser WebSocket` → `Svelte stores`. No polling.

### Process Isolation
In production, each user's data is fully isolated in separate OS processes with separate SQLite databases. The gateway is the only shared component.

---

## Need Help?

- **Architecture questions**: Start with `gateway.py` (production) or `api/app.py` (backend)
- **Agent behavior**: `agents/manager.py` + `agents/agent.py`
- **Frontend**: `+layout.svelte` for app shell, `ChatPanel.svelte` for chat
- **Deployment issues**: Check `fly.toml`, `Dockerfile`, and Fly.io logs
