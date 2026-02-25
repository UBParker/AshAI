# AshAI Setup Guide

## Prerequisites

- Docker Desktop installed and running
- Node.js 20+
- Python 3.11+
- A Claude subscription (for CLI authentication)

## 1. Build the Docker Container

```bash
docker build -f Dockerfile.consolidated-claude-cli -t ashai-claude-cli .
```

## 2. Configure Mounts

Copy the example mount config and edit it to point at your project directory:

```bash
cp mounts.conf.example mounts.conf
```

Edit `mounts.conf` — one mount per line, format is `host_path:container_path[:ro]`:

```
/path/to/your/project:/app/workspace
```

## 3. Start the Container

```bash
docker run -d \
  --name ashai-claude-cli \
  -p 8081:8081 \
  -p 8082:8082 \
  -p 2222:22 \
  -e ANTHROPIC_API_KEY=sk-ant-your-key-here \
  -v /path/to/AshAI:/app/workspace \
  ashai-claude-cli
```

> **Note:** The `ANTHROPIC_API_KEY` is passed to the container where the Anthropic API proxy runs.
> The host backend connects to the proxy at `localhost:8082` — the real key never leaves the container.

## 4. Install and Authenticate Claude CLI

SSH into the container, install Claude CLI, and log in:

```bash
ssh claude@localhost -p 2222
# Password: claude

# Install Claude CLI
curl -fsSL https://claude.ai/install.sh | bash

# Authenticate
claude login
# Follow the authentication prompts
```

## 5. Verify the Terminal Controller

The terminal controller starts automatically with the container. Verify it's ready:

```bash
curl http://localhost:8081/api/status
# Should show: {"claude_installed": true, "authenticated": true, ...}
```

## 6. Configure Environment

Copy the example env file and set the provider to `claude_terminal`:

```bash
cp .env.example .env
```

Edit `.env` and set:

```
HELPERAI_DEFAULT_PROVIDER=claude_terminal
HELPERAI_EVE_PROVIDER=anthropic
HELPERAI_EVE_MODEL=claude-sonnet-4-20250514
HELPERAI_ANTHROPIC_API_KEY=proxy
HELPERAI_ANTHROPIC_BASE_URL=http://localhost:8082
HELPERAI_PORT=8000
```

## 7. Install Backend Dependencies

```bash
pip install -e .
pip install docker aiohttp
```

## 8. Install Frontend Dependencies

```bash
cd src/frontend
npm install
cd ../..
```

## 9. Start the Backend

```bash
python -m helperai
```

The backend runs on http://localhost:8000.

## 10. Start the Frontend

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
| Terminal Controller | 8081 | 8081 | Claude CLI API |
| Anthropic Proxy | 8082 | 8082 | API key proxy for Anthropic |
| SSH | 2222 | 22 | Container access |
| Frontend | 5173 | — | Dev server |

## Troubleshooting

### Ash goes into error state
- Check the backend terminal for error logs
- Verify the container is authenticated: `curl http://localhost:8081/api/status`
- If auth is lost (container restarted), SSH in and run `claude login` again

### Frontend shows old agent / 404 errors
- Do a hard refresh (Cmd+Shift+R) after any DB reset

### "Provider not found" on startup
- Make sure `.env` has `HELPERAI_DEFAULT_PROVIDER=claude_terminal`
- Delete `helperai.db` and restart the backend to regenerate Ash with the correct provider

### Container can't reach the internet
- Check Docker Desktop is running
- Test from inside: `docker exec ashai-claude-cli curl -s https://platform.claude.com`

### Auth lost after container restart
- Claude CLI auth doesn't persist across container restarts
- SSH in (`ssh claude@localhost -p 2222`) and run `claude login` again
- Then restart the terminal controller: `docker exec -d ashai-claude-cli python3 /app/workspace/claude-terminal-controller.py`
