# AshAI Tool Development Guide

## Overview

Tools give agents the ability to take actions — spawn sub-agents, run commands, read files, interact with external services. Every tool implements the `Tool` protocol and is registered in the `ToolRegistry`.

## Tool Protocol

All tools must implement this interface (`src/helperai/tools/protocol.py`):

```python
from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext

class Tool(Protocol):
    @property
    def definition(self) -> ToolDefinition: ...

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str: ...
```

### ToolDefinition

Describes the tool to the LLM (used as a function definition in the API call):

```python
@dataclass
class ToolDefinition:
    name: str                    # Unique identifier (alphanumeric + underscores)
    description: str             # What the tool does (shown to the LLM)
    parameters: dict             # JSON Schema for arguments
    tool_type: str = "function"  # "function" or anthropic computer-use types
    extra: dict = {}             # Extra fields for specialized tools
```

### ToolContext

Runtime context passed to every tool invocation:

```python
@dataclass
class ToolContext:
    agent_id: str                          # ID of the agent calling the tool
    agent_manager: AgentManager            # Full access to agent lifecycle
    event_bus: EventBus                    # Emit events
    approval_manager: ApprovalManager | None  # Request user approval
```

## Built-in Tools

### `spawn_agent`
Create and start a new sub-agent. Automatically includes `report_to_eve` in the tool list.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Short descriptive name |
| `role` | string | yes | System prompt / persona |
| `goal` | string | yes | Task description |
| `tool_names` | string[] | no | Tools to assign |
| `initial_message` | string | no | First message (starts agent immediately) |
| `model` | string | no | Model override |
| `provider` | string | no | Provider override |

### `list_agents`
List all active (non-destroyed) agents. Returns agent ID, name, status, parent, and model info.

### `message_agent`
Send a message to another agent by ID.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | yes | Target agent ID |
| `message` | string | yes | Message content |

### `report_to_eve`
Send a report back to the parent agent (Ash/Eve). Automatically added to all spawned agents.

**Parameters:**
| Name | Type | Required | Description |
|---|---|---|---|
| `report` | string | yes | Report content |

## Creating a Custom Tool

### 1. Implement the Tool class

Create a new file in `src/helperai/tools/builtin/` or in a plugin:

```python
"""Tool: search the web."""

from __future__ import annotations

import json
from typing import Any

from helperai.llm.message_types import ToolDefinition
from helperai.tools.protocol import ToolContext


class WebSearchTool:
    # Optional: set to True to require user approval before execution
    requires_approval = False

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the web for information.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, arguments: dict[str, Any], ctx: ToolContext) -> str:
        query = arguments["query"]
        max_results = arguments.get("max_results", 5)

        # Your implementation here
        results = await do_search(query, max_results)

        return json.dumps({"results": results})
```

### 2. Register the tool

**Option A: Built-in tool** — Add to `src/helperai/api/app.py` in the lifespan function:

```python
from helperai.tools.builtin.web_search import WebSearchTool
tool_registry.register(WebSearchTool())
```

**Option B: Plugin** — See the Plugin section below.

### 3. Assign to agents

Tools are assigned to agents via the `tool_names` list when creating an agent:

```python
agent = await manager.create_agent(
    name="Researcher",
    role="You research topics on the web.",
    goal="Find information",
    tool_names=["web_search", "report_to_eve"],
)
```

## Tool Approval

Set `requires_approval = True` on your tool class to gate execution behind user approval. When the agent calls the tool:

1. An `approval_requested` SSE event is sent to the frontend
2. The agent pauses until the user approves or denies via `POST /api/approvals/{id}/approve` or `/deny`
3. If denied, the tool returns an error message to the LLM

## Plugin System

Plugins are Python packages in the `plugins/` directory (configurable via `HELPERAI_PLUGINS_DIR`).

### Plugin structure

```
plugins/
  my_plugin/
    __init__.py
    tools.py
```

### `__init__.py`

Must expose a `plugin` attribute:

```python
from helperai.tools.registry import ToolRegistry
from .tools import WebSearchTool


class MyPlugin:
    name = "My Plugin"
    description = "Adds web search capability"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(WebSearchTool())


plugin = MyPlugin()
```

### Plugin discovery

On startup, `load_plugins()` iterates subdirectories of `plugins/`, imports each package, and calls `plugin.register_tools(tool_registry)`. Failed plugins are logged and skipped.

## Signal File Bridge

External processes (e.g., Claude CLI agents in Docker) can interact with the tool system by writing JSON signal files:

```json
{
  "tool": "spawn_agent",
  "arguments": {
    "name": "Worker",
    "role": "assistant",
    "model": "claude-terminal",
    "tools": ["run_command", "report_to_eve"],
    "initial_message": "Start working on the task."
  }
}
```

Write to `.ashai_signal_<uuid>.json` in the watched directory. Supported tools: `spawn_agent`, `message_agent`, `report_to_ash`.

Bridge scripts are available in `ashai-tools/`:
- `spawn_agent.py` — Spawn agents via signal file + API
- `list_agents.py` — List agents via API
- `message_agent.py` — Message agents via signal file + API
