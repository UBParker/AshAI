# Docker Consolidation Report

## Executive Summary

Analyzed **11 Dockerfiles** in the AshAI workspace and consolidated them into **3 Dockerfiles** using multi-stage builds and build args. Fixed all `--break-system-packages` violations, added health checks to all containers, and ensured non-root user execution throughout.

---

## Original State: 11 Dockerfiles

### Inventory

| # | File | Base Image | Purpose | Issues |
|---|------|-----------|---------|--------|
| 1 | `Dockerfile` | python:3.12-slim + node:20-slim | Gateway (API + SPA) | Runs as root |
| 2 | `Dockerfile.playwright` | python:3.12-slim + node:20-slim | Gateway + Playwright | None (well-configured) |
| 3 | `Dockerfile.claude-browser` | node:20-alpine | Claude CLI + Chromium + VNC | `--break-system-packages`, no healthcheck |
| 4 | `Dockerfile.claude-x11` | node:20-alpine | Claude CLI + Chromium (X11) | `--break-system-packages`, no healthcheck |
| 5 | `Dockerfile.claude-final` | node:20-alpine | Claude CLI minimal | `--break-system-packages`, no healthcheck |
| 6 | `Dockerfile.claude-authenticated` | ashai-claude-cli:latest | Pre-auth Claude CLI | Inherits `--break-system-packages`, no healthcheck |
| 7 | `Dockerfile.claude-code` | ubuntu:22.04 | Desktop + VNC + Electron | No healthcheck |
| 8 | `Dockerfile.vnc-claude` | ubuntu:22.04 | VNC + Playwright + Chromium | Runs as root, no healthcheck |
| 9 | `Dockerfile.vnc-browser` | ubuntu:22.04 | VNC + Firefox + Playwright | No healthcheck |
| 10 | `Dockerfile.claude-session` | python:3.11-slim | Session API (aiohttp only) | Runs as root, no healthcheck |
| 11 | `Dockerfile.claude-cli` | ubuntu:22.04 | CLI + SSH + supervisor | No healthcheck |

### Issues Found

1. **`--break-system-packages` in 4 files** — `Dockerfile.claude-browser`, `.claude-x11`, `.claude-final`, `.claude-authenticated` all use `pip3 install aiohttp --break-system-packages` on Alpine. This bypasses PEP 668 protections and can corrupt the system Python.

2. **No health checks in 9 of 11 files** — Only `Dockerfile` and `Dockerfile.playwright` had health checks.

3. **Root execution in 4 files** — `Dockerfile`, `Dockerfile.vnc-claude`, `Dockerfile.claude-session` run as root. The main `Dockerfile` was the most critical since it's the production gateway.

4. **Massive duplication** — The 4 Alpine CLI variants share ~80% identical content. The 3 Ubuntu VNC variants share ~60% of packages.

5. **Inconsistent Python versions** — `python:3.12-slim` (gateway), `python:3.11-slim` (session), system python3 (all others).

---

## Consolidated State: 3 Dockerfiles

### 1. `Dockerfile.consolidated-gateway`
**Replaces:** `Dockerfile` + `Dockerfile.playwright`

| Build Arg | Default | Purpose |
|-----------|---------|---------|
| `WITH_PLAYWRIGHT` | `false` | Enable Playwright + Chromium |

**Build commands:**
```bash
# Standard gateway
docker build -f Dockerfile.consolidated-gateway -t ashai-gateway .

# Gateway + Playwright
docker build -f Dockerfile.consolidated-gateway --build-arg WITH_PLAYWRIGHT=true -t ashai-playwright .
```

**Improvements:**
- Always runs as non-root (`ashai` user)
- Health check always included
- Single file, ~50% less duplication

---

### 2. `Dockerfile.consolidated-claude-cli`
**Replaces:** `Dockerfile.claude-browser` + `Dockerfile.claude-x11` + `Dockerfile.claude-final` + `Dockerfile.claude-authenticated`

| Build Arg | Default | Purpose |
|-----------|---------|---------|
| `WITH_BROWSER` | `false` | Install Chromium + X11 deps |
| `WITH_VNC` | `false` | Add VNC server (requires WITH_BROWSER) |
| `WITH_AUTH` | `false` | Pre-authenticated mode |
| `WITH_SSH` | `false` | Add SSH server |

**Build commands:**
```bash
# Minimal CLI
docker build -f Dockerfile.consolidated-claude-cli -t ashai-claude-cli .

# CLI + Browser + VNC
docker build -f Dockerfile.consolidated-claude-cli --build-arg WITH_BROWSER=true --build-arg WITH_VNC=true -t ashai-claude-browser .

# CLI + Browser (X11 forwarding)
docker build -f Dockerfile.consolidated-claude-cli --build-arg WITH_BROWSER=true -t ashai-claude-x11 .
```

**Runtime modes:**
```bash
# Start API server (default)
docker run ashai-claude-cli server

# Run authentication flow
docker run ashai-claude-browser auth

# Mount pre-existing auth file
docker run -v ./claude-auth.json:/tmp/claude-auth.json ashai-claude-cli server
```

**Improvements:**
- **Fixed `--break-system-packages`** — uses `/opt/venv` virtual environment
- Health check on all variants
- Non-root user throughout
- Single entrypoint handles all modes

---

### 3. `Dockerfile.consolidated-claude-desktop`
**Replaces:** `Dockerfile.claude-code` + `Dockerfile.vnc-claude` + `Dockerfile.vnc-browser` + `Dockerfile.claude-session` + `Dockerfile.claude-cli`

| Build Arg | Default | Purpose |
|-----------|---------|---------|
| `BROWSER` | `chromium` | Browser to install (chromium/firefox) |
| `WITH_ELECTRON` | `false` | Add Electron desktop app deps |
| `WITH_SSH` | `false` | Add SSH server |
| `WITH_NODEJS` | `false` | Install Node.js 20 |
| `SESSION_ONLY` | `false` | Minimal session API (no browser/VNC) |

**Build commands:**
```bash
# VNC + Chromium (default)
docker build -f Dockerfile.consolidated-claude-desktop -t ashai-vnc-claude .

# VNC + Firefox
docker build -f Dockerfile.consolidated-claude-desktop --build-arg BROWSER=firefox -t ashai-vnc-firefox .

# Desktop app mode
docker build -f Dockerfile.consolidated-claude-desktop --build-arg WITH_ELECTRON=true -t ashai-claude-desktop .

# Session API only (minimal)
docker build -f Dockerfile.consolidated-claude-desktop --build-arg SESSION_ONLY=true -t ashai-session .

# CLI + SSH
docker build -f Dockerfile.consolidated-claude-desktop --build-arg WITH_SSH=true --build-arg WITH_NODEJS=true -t ashai-claude-ssh .
```

**Improvements:**
- **Fixed `--break-system-packages`** — uses `/opt/venv` virtual environment
- Health check on all variants
- Non-root user (`claude`) throughout
- Single entrypoint with mode selection

---

## Key Fixes Applied

### 1. `--break-system-packages` → Virtual Environments

**Before (broken):**
```dockerfile
RUN pip3 install aiohttp --break-system-packages
```

**After (proper):**
```dockerfile
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir aiohttp
```

This properly isolates pip packages in a virtual environment instead of forcing installation into the system Python, which could break system tools that depend on specific package versions.

### 2. Health Checks Added Everywhere

All 3 consolidated Dockerfiles now include `HEALTHCHECK` directives:
- Gateway: `curl -f http://localhost:9000/gateway/health`
- CLI: `curl -f http://localhost:8000/health`
- Desktop: `curl -f http://localhost:8080/health || curl -f http://localhost:8081/health`

### 3. Non-Root User Everywhere

All containers now run as non-root:
- Gateway: `ashai` user (with audio,video groups for Playwright)
- CLI: `claude` user
- Desktop: `claude` user (with audio,video groups)

---

## Migration Path

1. **Update `docker-compose.claude-agents.yml`** to reference consolidated Dockerfiles
2. **Update any CI/CD scripts** that reference old Dockerfile names
3. **Test each build variant** to ensure feature parity
4. **Remove old Dockerfiles** once validated

### Mapping: Old → New

| Old Dockerfile | New Build Command |
|---------------|-------------------|
| `Dockerfile` | `docker build -f Dockerfile.consolidated-gateway .` |
| `Dockerfile.playwright` | `docker build -f Dockerfile.consolidated-gateway --build-arg WITH_PLAYWRIGHT=true .` |
| `Dockerfile.claude-browser` | `docker build -f Dockerfile.consolidated-claude-cli --build-arg WITH_BROWSER=true --build-arg WITH_VNC=true .` |
| `Dockerfile.claude-x11` | `docker build -f Dockerfile.consolidated-claude-cli --build-arg WITH_BROWSER=true .` |
| `Dockerfile.claude-final` | `docker build -f Dockerfile.consolidated-claude-cli .` |
| `Dockerfile.claude-authenticated` | `docker build -f Dockerfile.consolidated-claude-cli .` + mount auth.json |
| `Dockerfile.claude-code` | `docker build -f Dockerfile.consolidated-claude-desktop --build-arg WITH_ELECTRON=true .` |
| `Dockerfile.vnc-claude` | `docker build -f Dockerfile.consolidated-claude-desktop .` |
| `Dockerfile.vnc-browser` | `docker build -f Dockerfile.consolidated-claude-desktop --build-arg BROWSER=firefox .` |
| `Dockerfile.claude-session` | `docker build -f Dockerfile.consolidated-claude-desktop --build-arg SESSION_ONLY=true .` |
| `Dockerfile.claude-cli` | `docker build -f Dockerfile.consolidated-claude-desktop --build-arg WITH_SSH=true --build-arg WITH_NODEJS=true .` |

---

## Resource Limits Recommendation

Add to `docker-compose.yml` for each service:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

For Playwright/VNC containers, increase to:
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 4G
    reservations:
      cpus: '1.0'
      memory: 1G
```

These should be added to `docker-compose.claude-agents.yml` per service.
