# VNC + Playwright Claude Integration

## Overview
Since direct cookie-based authentication doesn't work with Claude.ai's API (returns 404 errors), we're using a VNC + Playwright approach:

1. **VNC Container**: Provides a remote desktop with Chrome browser
2. **Manual Login**: You log into Claude.ai through VNC viewer
3. **Playwright Controller**: Connects to the authenticated browser session and automates interactions

## Setup Instructions

### 1. Build and Run VNC Container
```bash
# Build the container
docker build -f Dockerfile.vnc-browser -t claude-vnc .

# Run it
docker run -d \
  --name claude-vnc \
  -p 5900:5900 \
  -p 8081:8081 \
  claude-vnc
```

### 2. Connect via VNC
```bash
# On macOS, use the built-in VNC viewer
open vnc://localhost:5900
# Password: changeme
```

### 3. Log into Claude.ai
1. In the VNC session, Chrome will be running
2. Navigate to https://claude.ai
3. Log in with your credentials
4. Stay on the Claude.ai chat interface

### 4. Test the Playwright API
```bash
# Check authentication status
curl http://localhost:8081/api/status

# Send a message
curl -X POST http://localhost:8081/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Claude!"}'
```

## How It Works

1. **VNC Server**: Runs Xvfb (virtual display) + x11vnc for remote access
2. **Chrome Browser**: Runs with `--remote-debugging-port=9222` for Playwright connection
3. **Playwright Controller**:
   - Connects to Chrome via CDP (Chrome DevTools Protocol)
   - Automates sending messages and extracting responses
   - Provides HTTP API on port 8081

## Integration with AshAI

The Playwright controller API (port 8081) can be integrated with AshAI as a new provider, similar to how we tried with the session provider but this time with a working authenticated browser.

## Advantages

- **Uses your $20/month subscription** instead of expensive API ($15/million tokens)
- **No authentication issues** - you log in manually through the browser
- **Reliable** - Playwright controls a real browser session
- **Cost savings**: $560+/month saved vs API pricing

## Files Created

- `Dockerfile.vnc-browser` - VNC container with Chrome
- `vnc-supervisor.conf` - Supervisor config for all services
- `claude-playwright-controller.py` - Playwright automation script
- `claude-integration-options.md` - Alternative approaches analyzed