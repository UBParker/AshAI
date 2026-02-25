# Claude Code Integration Strategy for AshAI

## The Challenge
Claude Code (desktop app) doesn't expose a traditional API that containers can connect to. It's a standalone Electron app that uses Anthropic's internal APIs with your subscription authentication.

## Better Solution: Hybrid Approach

### Option 1: Direct Anthropic API with Subscription
Instead of trying to integrate Claude Code, use your Anthropic subscription directly:

1. **Your subscription includes API access** - Claude Pro/Team subscriptions come with API credits
2. **Use the standard Anthropic API** in AshAI (which is already implemented)
3. **Much simpler and more reliable** than trying to bridge desktop apps

### Option 2: Local Development + Containerized Deployment

**For Local Development:**
- Use Claude Code directly on your machine (as you're doing now)
- Run AshAI locally to coordinate agents
- Best performance and developer experience

**For Production/Sharing:**
```yaml
# docker-compose.yml
version: '3.8'
services:
  ashai:
    image: ashai:latest
    environment:
      - HELPERAI_ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - HELPERAI_DEFAULT_PROVIDER=anthropic
      - HELPERAI_DEFAULT_MODEL=claude-3-5-sonnet-20241022
    ports:
      - "9000:9000"
    volumes:
      - ./data:/data
```

### Option 3: MCP (Model Context Protocol) Integration

Claude Code supports MCP servers. We could:
1. **Build AshAI as an MCP server** that Claude Code can connect to
2. **Claude Code would control AshAI agents** through MCP
3. **Agents could then coordinate tasks** while you work in Claude Code

This is the most elegant solution - making AshAI augment Claude Code rather than trying to containerize it.

## Recommended Architecture

```
┌─────────────────┐
│  Claude Code    │  <- Your subscription/desktop app
│  (Desktop App)  │
└────────┬────────┘
         │ MCP Protocol
         ▼
┌─────────────────┐
│   AshAI MCP     │  <- Bridge between Claude and agents
│    Server       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent Fleet    │  <- Specialized agents doing work
│  (Container)    │
└─────────────────┘
```

## Implementation Plan

### Phase 1: MCP Server for AshAI
Create an MCP server that exposes AshAI's agent coordination capabilities to Claude Code.

```python
# src/helperai/mcp/server.py
from mcp import Server, Tool

class AshAIMCPServer(Server):
    """MCP server exposing AshAI agents to Claude Code"""

    @tool()
    async def spawn_agent(self, name: str, role: str, goal: str):
        """Spawn a new AshAI agent"""
        # Create agent through AshAI
        pass

    @tool()
    async def coordinate_agents(self, task: str):
        """Coordinate multiple agents for complex tasks"""
        # Use AshAI's orchestration
        pass
```

### Phase 2: Configure Claude Code
Add AshAI as an MCP server in Claude Code settings:

```json
{
  "mcpServers": {
    "ashai": {
      "command": "docker",
      "args": ["run", "-p", "3000:3000", "ashai-mcp-server"]
    }
  }
}
```

### Phase 3: Lightweight Container
Build a minimal container just for the MCP bridge:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY src/helperai/mcp /app/mcp
RUN pip install mcp anthropic
CMD ["python", "-m", "mcp.server"]
```

## Benefits of This Approach

1. **Uses your Claude subscription naturally** - through the desktop app
2. **Lightweight containers** - only ~200MB instead of 2.5GB
3. **Better integration** - Claude Code can directly control agents
4. **No browser automation** - clean, reliable API calls
5. **Local + cloud hybrid** - develop locally, deploy anywhere

## Quick Start (Current Best Practice)

For now, the optimal setup is:

1. **Keep using Claude Code** for development (free tier or subscription)
2. **Run AshAI locally** with your API key:
   ```bash
   python -m helperai
   ```
3. **Use Docker only for deployment** when sharing with others

This gives you the best of both worlds without the complexity of browser automation or trying to containerize desktop applications.

## Next Steps

1. Research MCP protocol implementation details
2. Create minimal MCP server for AshAI
3. Test integration with Claude Code
4. Build lightweight container (200MB vs 2.5GB)
5. Document configuration for end users

This approach aligns with how Claude Code is designed to work - as a desktop app that can connect to external tools via MCP, rather than trying to force it into a container.