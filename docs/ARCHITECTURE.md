# AshAI Architecture

## System Overview

AshAI is a multi-agent AI framework with a FastAPI backend, Svelte 5 frontend, and optional Tauri desktop shell. It follows a hub-and-spoke architecture where a master agent ("Ash") coordinates sub-agents that each have their own conversation threads, tools, and LLM providers.

```
                          +------------------+
                          |   Svelte 5 SPA   |
                          | (Frontend/Tauri) |
                          +--------+---------+
                                   |
                          REST + SSE + WebSocket
                                   |
                  +----------------+----------------+
                  |         Gateway (optional)       |
                  |  JWT auth, reverse proxy, spawn  |
                  |  per-user backend instances       |
                  +----------------+----------------+
                                   |
                  +----------------+----------------+
                  |         FastAPI Backend          |
                  |  (helperai.api.app)              |
                  +----------------+----------------+
                          |                |
               +----------+----------+     |
               |    AgentManager     |     |
               | lifecycle, queues,  |     |
               | message routing     |     |
               +----+------+--------+     |
                    |      |              |
           +--------+  +--+-------+   +--+--------+
           |  Ash   |  | SubAgent |   | EventBus  |
           | (Eve)  |  |   ...    |   |  pub/sub  |
           +--------+  +----------+   +-----------+
                    |
         +----------+-----------+
         |  LLMRegistry  |  ToolRegistry  |
         +---------------+----------------+
```

## Core Components

### Agent System (`src/helperai/agents/`)

- **ConversationalAgent** (`agent.py`) — The core agent run loop. Maintains a message history, streams LLM responses, executes tool calls in a loop (up to 35 rounds per step), and handles the approval gate for sensitive tools.

- **AgentManager** (`manager.py`) — Lifecycle manager for all agents. Handles create, start, message, cancel, and destroy operations. Features:
  - Message queuing when an agent is busy (RUNNING state)
  - Thread-safe message delivery via `threading.Lock` to prevent TOCTOU races
  - Background queue processing after each response completes
  - Cancellation flags for interrupting running agents
  - Knowledge base injection into Ash's system prompt

- **Eve/Ash** (`eve.py`) — System prompt and tool configuration for the master agent. Ash is the coordinator that spawns and manages sub-agents.

- **State machine** (`state.py`) — Validates agent status transitions according to the rules defined in `core/types.py`.

### Agent Lifecycle

```
CREATED ──> RUNNING ──> IDLE ──> RUNNING ──> ...
   │           │          │
   │           ├──> WAITING_FOR_USER ──> RUNNING
   │           │
   │           ├──> COMPLETED ──> RUNNING (restart)
   │           │
   │           └──> ERROR ──> RUNNING (retry)
   │
   └──> IDLE (start_agent)
   └──> DESTROYED (terminal)
```

Valid transitions are enforced by `VALID_TRANSITIONS` in `core/types.py`. `DESTROYED` is terminal — no transitions out.

### Message Flow

1. **User sends message** via `POST /api/chat` or `POST /api/agents/{id}/message`
2. **AgentManager.send_message_stream()** checks if agent is busy:
   - If RUNNING: queues message, saves to DB, yields `{"type": "queued"}`
   - If IDLE: sets status to RUNNING, processes immediately
3. **ConversationalAgent.step_stream()** runs the LLM loop:
   - Streams LLM response tokens as `{"type": "content", "text": "..."}`
   - If LLM returns tool calls: executes each, appends results, loops back
   - If tool requires approval: yields `{"type": "approval_requested"}`, waits
   - When done (no more tool calls): yields `{"type": "done"}`
4. **Messages saved to DB** — all new messages (assistant, tool results) are persisted
5. **Status set to IDLE** — or ERROR if an exception occurred
6. **Queue processed** — any queued messages are processed sequentially

### Event System (`src/helperai/core/events.py`)

An async pub/sub `EventBus` broadcasts real-time events:

| Event Type | When |
|---|---|
| `agent.created` | New agent created |
| `agent.status_changed` | Status transition |
| `agent.message` | Injected message (e.g., sub-agent report) |
| `agent.stream_chunk` | LLM token during streaming |
| `agent.stream_end` | LLM response complete |
| `agent.destroyed` | Agent destroyed |
| `agent.error` | Agent error |
| `approval.requested` | Tool needs user approval |
| `approval.resolved` | User approved/denied |

Events are delivered to the frontend via WebSocket (`/api/ws`). The WebSocket endpoint registers a global listener that forwards all events as JSON.

### LLM Providers (`src/helperai/llm/`)

All providers implement the `LLMProvider` protocol:

```python
class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...
    async def stream(self, messages, model, *, temperature, tools) -> AsyncIterator[StreamChunk]: ...
    async def list_models(self) -> list[str]: ...
```

Registered providers (configured via environment variables):
- **ollama** — Local models via OpenAI-compatible API
- **openai** — OpenAI API
- **anthropic** — Anthropic API (native)
- **claude_docker** — Claude CLI in Docker containers
- **claude_host** — Host's Claude CLI directly
- **claude_terminal** — Claude CLI via terminal API
- **claude_session** — Browser cookie-based access
- **claude_web** — Playwright-based web automation (legacy)

The `LLMRegistry` maps provider names to instances and tracks a default.

### Tool System (`src/helperai/tools/`)

Tools implement the `Tool` protocol:

```python
class Tool(Protocol):
    @property
    def definition(self) -> ToolDefinition: ...
    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str: ...
```

`ToolContext` provides access to `agent_id`, `agent_manager`, `event_bus`, and `approval_manager`.

Built-in tools: `spawn_agent`, `list_agents`, `message_agent`, `report_to_eve`.

### Plugin System (`src/helperai/plugins/`)

Plugins are Python packages in the `plugins/` directory. Each must expose a `plugin` attribute with:
- `plugin.name` — display name
- `plugin.description` — short description
- `plugin.register_tools(tool_registry)` — registers tools

### Gateway (`src/helperai/gateway.py`)

The gateway is a multi-tenant proxy that:
1. Validates Supabase JWTs
2. Spawns per-user or per-project AshAI backend instances as subprocesses
3. Reverse-proxies all `/api/*` requests and WebSocket connections
4. Reaps idle instances (personal: 30 min, project with no users: 15 min)
5. Serves the SPA frontend for all non-API routes

### Signal File Monitor (`src/helperai/signal_monitor.py`)

Enables external processes (like Claude CLI in Docker) to interact with agents by writing JSON signal files. The monitor uses `watchdog` to detect new `.ashai_signal_*.json` files and processes `spawn_agent`, `message_agent`, and `report_to_ash` commands.

### Configuration (`src/helperai/config.py`)

Uses `pydantic-settings` with `HELPERAI_` environment variable prefix. Key settings:
- `default_provider` / `default_model` — LLM defaults
- Provider API keys and URLs
- `eve_name` — master agent name (default: "Ash")
- `plugins_dir` — plugin directory path
- `cors_origins` — allowed CORS origins

### Database

SQLite via `aiosqlite` + SQLAlchemy async. Models:
- `Agent` — id, name, role, goal, status, parent_id, provider_name, model_name, tool_names
- `ThreadMessage` — agent_id, role, content, tool_calls, tool_call_id, sender_name, sequence
- `KnowledgeEntry` — title, content, added_by, timestamps

### Frontend (`src/frontend/`)

Svelte 5 SPA with SvelteKit (static adapter for Tauri). Key features:
- Real-time streaming via SSE (chat) and WebSocket (events)
- Agent management UI (create, configure, destroy)
- Knowledge base editor
- Provider/model selection
- Supabase auth (optional, for hosted mode)

### Desktop App (`src-tauri/`)

Tauri 2 wrapper that bundles the frontend SPA and can optionally run the backend as a sidecar process.
