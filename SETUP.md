# AshAI Setup Guide

## Prerequisites

- Docker Desktop installed and running
- Node.js 20+
- Python 3.11+
- A Claude subscription (for CLI authentication)
- (Optional) Gemini API key for Gemini CLI models

## 1. Build the Docker Container

```bash
docker build -f Dockerfile.consolidated-claude-cli -t ashai-claude-cli .
```

The image includes both Claude CLI and Gemini CLI pre-installed.

## 2. Start the Container

Using docker-compose (recommended):

```bash
docker compose up -d
```

Or manually:

```bash
docker run -d \
  --name ashai-claude-cli \
  -p 8081:8081 \
  -p 8082:8082 \
  -p 2222:22 \
  -e ANTHROPIC_API_KEY=sk-ant-your-key-here \
  -e GEMINI_API_KEY=your-gemini-key-here \
  -v /path/to/AshAI:/app/workspace \
  ashai-claude-cli
```

> **Note:** API keys are passed to the container where the multi-provider proxy runs.
> The host backend connects to the proxy at `localhost:8082` — real keys never leave the container.

## 3. Authenticate Claude CLI

SSH into the container and log in:

```bash
ssh claude@localhost -p 2222
# Password: claude

claude login
# Follow the authentication prompts
```

## 4. Verify the CLI Agent Controller

The controller starts automatically and discovers installed CLIs. Verify:

```bash
curl http://localhost:8081/api/status
# Should show: {"installed_clis": ["claude", "gemini"], "models": [...], "ready": true}

curl http://localhost:8081/api/models
# Returns all available models with their CLI backend
```

Available models (when both CLIs are installed):

| Model | CLI Backend |
|-------|-------------|
| `claude-sonnet-4` | claude |
| `claude-opus-4` | claude |
| `claude-haiku-3.5` | claude |
| `gemini-2.5-pro` | gemini |
| `gemini-2.5-flash` | gemini |
| `gemini-2.0-flash` | gemini |

## 5. Configure Environment

Copy the example env file:

```bash
cp .env.example .env
```

Edit `.env` and set:

```
HELPERAI_DEFAULT_PROVIDER=cli_agent
HELPERAI_DEFAULT_MODEL=claude-sonnet-4
HELPERAI_EVE_PROVIDER=anthropic
HELPERAI_EVE_MODEL=claude-sonnet-4-20250514
HELPERAI_ANTHROPIC_API_KEY=proxy
HELPERAI_ANTHROPIC_BASE_URL=http://localhost:8082
HELPERAI_PORT=8000
```

> The `cli_agent` provider routes to the right CLI based on the model name.
> It is backward-compatible with `claude_terminal` — both names work.

## 6. Install Backend Dependencies

```bash
pip install -e .
pip install docker aiohttp
```

## 7. Install Frontend Dependencies

```bash
cd src/frontend
npm install
cd ../..
```

## 8. Start the Backend

```bash
python -m helperai
```

The backend runs on http://localhost:8000.

## 9. Start the Frontend

In a separate terminal:

```bash
cd src/frontend
npm run dev
```

The frontend runs on http://localhost:5173. Open it in your browser and message Ash.

---

## Port Reference

| Service | Host Port | Container Port | Purpose |
|---------|-----------|---------------|---------|
| Backend API | 8000 | — | AshAI backend |
| CLI Agent Controller | 8081 | 8081 | Routes model requests to CLIs |
| Multi-Provider Proxy | 8082 | 8082 | API key proxy (Anthropic, OpenAI, Gemini) |
| SSH | 2222 | 22 | Container access |
| Frontend | 5173 | — | Dev server |

## Troubleshooting

### Ash goes into error state
- Check the backend terminal for error logs
- Verify the controller is ready: `curl http://localhost:8081/api/status`
- If Claude auth is lost (container restarted), SSH in and run `claude login` again

### Frontend shows old agent / 404 errors
- Do a hard refresh (Cmd+Shift+R) after any DB reset

### "Provider not found" on startup
- Make sure `.env` has `HELPERAI_DEFAULT_PROVIDER=cli_agent`
- Delete `helperai.db` and restart the backend to regenerate Ash with the correct provider

### Container can't reach the internet
- Check Docker Desktop is running
- Test from inside: `docker exec ashai-claude-cli curl -s https://platform.claude.com`

### Auth lost after container restart
- Claude CLI auth doesn't persist across container restarts
- SSH in (`ssh claude@localhost -p 2222`) and run `claude login` again

### A model shows "CLI not installed"
- Check which CLIs are available: `curl http://localhost:8081/api/status`
- Only models whose CLI is installed will appear in `GET /api/models`
