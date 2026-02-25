# AshAI API Reference

Base URL: `http://localhost:8000` (local) or proxied through the gateway at port 9000.

## REST Endpoints

### Health

#### `GET /api/health`
Returns server status.

**Response:**
```json
{ "status": "ok", "version": "0.1.0" }
```

#### `GET /api/instance-info`
Returns instance metadata (personal vs. project mode).

**Response:**
```json
{ "instance_type": "personal", "project_id": null }
```

---

### Chat

#### `POST /api/chat`
Send a message to Ash (or a specific agent). Returns an SSE stream.

**Request body:**
```json
{
  "message": "Hello, Ash!",
  "agent_id": null,
  "sender_name": "Alice"
}
```

- `message` (required) — Up to 100,000 characters.
- `agent_id` (optional) — Target agent. Defaults to Ash.
- `sender_name` (optional) — Display name for shared projects. Max 100 chars.

**SSE events:**

| Event | Data | Description |
|---|---|---|
| `content` | `{"type": "content", "text": "..."}` | Streamed token |
| `tool_call` | `{"type": "tool_call", "name": "...", "arguments": {...}}` | Tool invocation |
| `tool_result` | `{"type": "tool_result", "name": "...", "result": "..."}` | Tool output |
| `approval_requested` | `{"type": "approval_requested", "name": "...", "arguments": {...}}` | Awaiting user approval |
| `done` | `{"type": "done"}` | Response complete |
| `queued` | `{"type": "queued", "position": 1}` | Message queued (agent busy) |
| `cancelled` | `{"type": "cancelled", "message": "..."}` | Response cancelled |
| `error` | `{"type": "error", "error": "..."}` | Error occurred |

---

### Agents

#### `GET /api/agents`
List all non-destroyed agents.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Ash",
    "role": "You are Ash...",
    "goal": "Help the user with any task.",
    "status": "idle",
    "parent_id": null,
    "provider_name": "ollama",
    "model_name": "llama3.2",
    "tool_names": ["spawn_agent", "list_agents", "message_agent", "report_to_eve"],
    "created_at": "2026-02-25T00:00:00"
  }
]
```

#### `POST /api/agents`
Create and auto-start a new agent. If no `parent_id`, defaults to Ash as parent.

**Request body:**
```json
{
  "name": "Coder",
  "role": "You are a coding assistant.",
  "goal": "Write clean Python code.",
  "provider_name": "anthropic",
  "model_name": "claude-sonnet-4-6",
  "tool_names": ["run_command", "report_to_eve"],
  "parent_id": null
}
```

Validation:
- `name`: 1-100 chars, alphanumeric + spaces/hyphens/underscores
- `role`: max 10,000 chars
- `goal`: max 10,000 chars
- `tool_names`: max 50 tools, each alphanumeric + underscores

#### `GET /api/agents/{agent_id}`
Get a single agent by ID.

#### `PUT /api/agents/{agent_id}`
Update agent properties. Cannot edit the master agent's name/role/goal. If the agent is running in memory, it will be restarted to apply changes.

**Request body** (all fields optional):
```json
{
  "name": "New Name",
  "role": "Updated role",
  "goal": "Updated goal",
  "provider_name": "openai",
  "model_name": "gpt-4",
  "tool_names": ["spawn_agent"],
  "parent_id": "parent-uuid"
}
```

#### `DELETE /api/agents/{agent_id}`
Destroy an agent. Cannot destroy Ash. Returns `{"status": "destroyed"}`.

#### `GET /api/agents/{agent_id}/thread`
Get the full message thread for an agent, ordered by sequence number.

**Response:**
```json
[
  {
    "id": "uuid",
    "role": "user",
    "content": "Hello",
    "tool_calls": null,
    "tool_call_id": null,
    "sender_name": "Alice",
    "sequence": 1,
    "created_at": "2026-02-25T00:00:00"
  }
]
```

#### `POST /api/agents/{agent_id}/message`
Send a message to a specific agent. Auto-starts the agent if not in memory. Returns the same SSE stream as `POST /api/chat`.

**Request body:**
```json
{
  "message": "Please review this code.",
  "sender_name": "Bob"
}
```

#### `POST /api/agents/{agent_id}/cancel`
Cancel the current operation for an agent.

**Response:**
```json
{ "status": "cancelled", "message": "Agent operation cancelled" }
```
or
```json
{ "status": "not_running", "message": "Agent was not running" }
```

---

### Providers

#### `GET /api/providers`
List registered LLM providers.

**Response:**
```json
[
  { "name": "ollama", "is_default": true },
  { "name": "anthropic", "is_default": false }
]
```

#### `GET /api/providers/{name}/models`
List available models for a provider.

**Response:**
```json
{ "provider": "ollama", "models": ["llama3.2", "codellama"] }
```

---

### Tools

#### `GET /api/tools`
List registered tools.

**Response:**
```json
[
  {
    "name": "spawn_agent",
    "description": "Create and start a new sub-agent...",
    "requires_approval": false
  }
]
```

---

### Knowledge Base

#### `GET /api/knowledge`
List all knowledge entries (newest first).

#### `POST /api/knowledge`
Add a knowledge entry. Refreshes Ash's system prompt automatically.

**Request body:**
```json
{
  "title": "Project Architecture",
  "content": "The project uses a microservices architecture...",
  "added_by": "Alice"
}
```

#### `PUT /api/knowledge/{entry_id}`
Update a knowledge entry.

**Request body:**
```json
{
  "title": "Updated Title",
  "content": "Updated content"
}
```

#### `DELETE /api/knowledge/{entry_id}`
Delete a knowledge entry.

---

### Approvals

#### `GET /api/approvals`
List pending tool approval requests.

#### `POST /api/approvals/{approval_id}/approve`
Approve a pending tool execution.

#### `POST /api/approvals/{approval_id}/deny`
Deny a pending tool execution.

---

### Settings

#### `GET /api/settings`
Get current configuration (sensitive keys masked).

**Response:**
```json
{
  "default_provider": "ollama",
  "default_model": "llama3.2",
  "has_anthropic_key": false,
  "has_openai_key": false,
  "has_gemini_key": false,
  "ollama_base_url": "http://localhost:11434",
  "eve_name": "Ash",
  "has_any_key": false,
  "env_file": "/path/to/.env"
}
```

#### `PUT /api/settings`
Write key/value pairs to `.env` and update the running environment. Keys are auto-prefixed with `HELPERAI_` if not already.

**Request body:**
```json
{
  "default_provider": "anthropic",
  "anthropic_api_key": "sk-ant-..."
}
```

#### `GET /api/settings/claude-cli`
Check if the Claude CLI is available on PATH.

**Response:**
```json
{
  "available": true,
  "path": "/usr/local/bin/claude",
  "install_url": "https://docs.anthropic.com/en/docs/claude-code/overview"
}
```

---

## WebSocket Protocol

### `WS /api/ws`

Connect to receive real-time agent events. In gateway mode, pass `?token=JWT&project_id=ID` as query parameters.

**Event format:**
```json
{
  "type": "agent.stream_chunk",
  "agent_id": "uuid",
  "data": { "text": "Hello" },
  "timestamp": "2026-02-25T00:00:00+00:00"
}
```

Event types match the `EventType` enum — see [ARCHITECTURE.md](ARCHITECTURE.md#event-system) for the full list.

---

## Gateway Endpoints

When running in hosted mode, the gateway adds these endpoints:

#### `POST /gateway/session`
Create or resume a personal backend instance. Requires `Authorization: Bearer <JWT>`.

#### `POST /gateway/project-session`
Create or resume a shared project instance. Body: `{"project_id": "uuid"}`.

#### `POST /gateway/leave-project`
Disconnect from a project instance. Body: `{"project_id": "uuid"}`.

#### `POST /gateway/logout`
Stop the user's personal backend instance.

#### `GET /gateway/health`
Gateway health check. Returns instance counts.

All `/api/*` requests are reverse-proxied to the user's backend instance. The gateway adds SSE streaming support for chat endpoints.
