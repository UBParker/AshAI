# helperAI

Open-source personal AI agent platform. Talk to **Eve**, a master agent who spawns specialized sub-agents for any task.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your provider settings

# Run
python -m helperai

# Test
pytest tests/ -v
```

## Architecture

- **Eve** — master agent the user chats with
- **Sub-agents** — spawned by Eve for specialized tasks, each with own thread
- **FastAPI** backend with SSE streaming and WebSocket events
- **SvelteKit** frontend with agent sidebar and chat UI
- **Provider-agnostic** — works with Ollama, OpenAI, Anthropic, or any OpenAI-compatible endpoint

## Frontend

```bash
cd src/frontend
npm install
npm run dev
```

The frontend dev server proxies `/api` requests to the backend at `localhost:8000`.
