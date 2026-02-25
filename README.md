# AshAI

Open-source AI coding assistant — provider-agnostic, extensible, local-first.

## Features

- **Multi-agent orchestration** — A master agent (Ash) spawns and coordinates sub-agents, each with their own tools and LLM providers
- **Provider-agnostic** — Supports Ollama, OpenAI, Anthropic, Claude CLI, and custom providers
- **Real-time streaming** — SSE for chat responses, WebSocket for agent events
- **Plugin system** — Extend with custom tools via a simple Python protocol
- **Knowledge base** — Persistent project knowledge injected into the master agent's context
- **Multi-tenant gateway** — Optional hosted mode with Supabase auth and per-user backend instances
- **Desktop app** — Tauri 2 wrapper for native desktop experience

## Quick Start

```bash
# Backend
pip install -e .
python -m helperai.desktop_main

# Frontend
cd src/frontend && npm install && npm run dev
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full setup instructions.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — System overview, agent lifecycle, message flow, component descriptions
- [API Reference](docs/API.md) — REST endpoints, SSE events, WebSocket protocol, gateway endpoints
- [Tool Development](docs/TOOLS.md) — Tool protocol, built-in tools, creating custom tools, plugin system
- [Deployment](docs/DEPLOYMENT.md) — Local dev, Docker, Fly.io, Tauri desktop, environment variables

## Project Structure

```
src/helperai/          # Python backend
  agents/              # Agent lifecycle and run loop
  api/                 # FastAPI routes
  core/                # Types, events, exceptions
  llm/                 # LLM provider protocol and implementations
  tools/               # Tool protocol, registry, built-in tools
  plugins/             # Plugin loader
  config.py            # Pydantic settings
  gateway.py           # Multi-tenant gateway proxy
  signal_monitor.py    # External process bridge
src/frontend/          # Svelte 5 SPA
src-tauri/             # Tauri desktop shell
```
