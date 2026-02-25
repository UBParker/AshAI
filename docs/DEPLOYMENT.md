# AshAI Deployment Guide

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- (Optional) Ollama for local LLM inference

### Backend

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your provider keys

# Run
python -m helperai.desktop_main
# Backend starts on http://localhost:8000
```

### Frontend

```bash
cd src/frontend
npm install
npm run dev
# Dev server starts on http://localhost:5173
```

### Environment Variables

All prefixed with `HELPERAI_`:

| Variable | Default | Description |
|---|---|---|
| `HELPERAI_HOST` | `127.0.0.1` | Backend bind address |
| `HELPERAI_PORT` | `8000` | Backend port |
| `HELPERAI_LOG_LEVEL` | `info` | Logging level |
| `HELPERAI_DATABASE_URL` | `sqlite+aiosqlite:///./helperai.db` | Database connection string |
| `HELPERAI_DEFAULT_PROVIDER` | `ollama` | Default LLM provider |
| `HELPERAI_DEFAULT_MODEL` | `llama3.2` | Default model name |
| `HELPERAI_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `HELPERAI_OPENAI_API_KEY` | (empty) | OpenAI API key |
| `HELPERAI_ANTHROPIC_API_KEY` | (empty) | Anthropic API key |
| `HELPERAI_EVE_NAME` | `Ash` | Master agent display name |
| `HELPERAI_EVE_MODEL` | (empty) | Override model for master agent |
| `HELPERAI_PLUGINS_DIR` | `plugins` | Plugin directory |
| `HELPERAI_CLAUDE_CODE_ENABLED` | `true` | Enable Claude Docker provider |

---

## Docker

### Single Instance (Dockerfile.main)

Builds both frontend and backend into a single image. Used for the gateway deployment.

```bash
# Build
docker build -f Dockerfile.main -t ashai-gateway \
  --build-arg VITE_SUPABASE_URL=https://your-project.supabase.co \
  --build-arg VITE_SUPABASE_ANON_KEY=your-anon-key \
  .

# Run
docker run -p 9000:9000 \
  -e HELPERAI_DEFAULT_PROVIDER=anthropic \
  -e HELPERAI_ANTHROPIC_API_KEY=sk-ant-... \
  -v ./data:/data \
  ashai-gateway
```

The image:
1. Builds the Svelte frontend in a Node.js stage
2. Installs the Python backend with `[gateway]` extras
3. Copies the built SPA to `/app/static`
4. Runs the gateway on port 9000 as a non-root user
5. Includes a health check at `/gateway/health`

### Multi-Agent Docker Compose

`docker-compose.claude-agents.yml` sets up the orchestrator + Claude agent containers:

```bash
docker compose -f docker-compose.claude-agents.yml up
```

Services:
- **ashai-orchestrator** — Gateway + frontend on port 9000. Mounts Docker socket to spawn agent containers.
- **claude-agent-1/2/3** — Pre-configured Claude CLI agents (Architect, Developer, Reviewer) with VNC access for debugging.

Resource limits per agent: 1 CPU, 2GB RAM.

---

## Fly.io

The project includes a `fly.toml` for deploying the gateway to Fly.io.

### Configuration

```toml
app = 'ashai-gateway'
primary_region = 'iad'

[build]
  dockerfile = 'Dockerfile'

[env]
  GATEWAY_DATA_DIR = '/data'
  GATEWAY_PORT = '9000'

[[mounts]]
  source = 'ashai_data'
  destination = '/data'

[[vm]]
  size = 'shared-cpu-2x'
  memory = '1024mb'
```

### Deploy

```bash
# First time
fly launch

# Set secrets
fly secrets set SUPABASE_URL=https://your-project.supabase.co
fly secrets set SUPABASE_SERVICE_KEY=your-service-key
fly secrets set HELPERAI_ANTHROPIC_API_KEY=sk-ant-...

# Deploy
fly deploy --build-arg VITE_SUPABASE_URL=... --build-arg VITE_SUPABASE_ANON_KEY=...
```

Key details:
- Persistent volume mounted at `/data` for SQLite databases
- Always-on (auto_stop = off, min_machines = 1)
- Health check at `/gateway/health` every 30s
- Shared CPU, 1GB RAM (sufficient for gateway + a few backend instances)
- Ports 80/443 with TLS termination

### Gateway Architecture on Fly.io

The gateway runs as a single process that:
1. Validates Supabase JWTs on every request
2. Spawns per-user backend subprocesses (ports 10001-10100)
3. Proxies API requests and WebSocket connections
4. Reaps idle instances (personal: 30 min, project: 15 min)
5. All data stored in `/data/users/<user_id>/` and `/data/projects/<project_id>/`

---

## Tauri Desktop App

The Tauri app wraps the frontend SPA and can run the backend locally.

```bash
cd src-tauri
cargo tauri dev     # Development
cargo tauri build   # Production build
```

The desktop app connects to `http://localhost:8000` by default, or to a remote gateway URL configured via environment variables.

---

## Production Checklist

- [ ] Set all API keys via environment variables (never in code)
- [ ] Configure Supabase for auth (gateway mode)
- [ ] Set `HELPERAI_LOG_LEVEL=warning` for production
- [ ] Ensure persistent volume for `/data` (SQLite databases)
- [ ] Configure CORS origins for your domain
- [ ] Review resource limits for agent containers
- [ ] Set up health check monitoring
