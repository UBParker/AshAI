# AshAI — single container serving both gateway (API) and frontend (static SPA).
# The gateway spawns per-user/project backend subprocesses with their own SQLite DBs.

# --- Stage 1: Build frontend ---
FROM node:20-slim AS frontend-build

WORKDIR /app/src/frontend

COPY src/frontend/package.json src/frontend/package-lock.json* ./
RUN npm install

COPY src/frontend/ ./

# Frontend env vars are baked in at build time
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
# Gateway URL is empty — frontend is served from the same origin
ARG VITE_GATEWAY_URL=""

RUN npm run build

# --- Stage 2: Python backend + static files ---
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files needed for install
COPY pyproject.toml README.md ./
COPY src/helperai/ ./src/helperai/

# Install the package with gateway extras
RUN pip install --no-cache-dir ".[gateway]"

# Copy built frontend from stage 1
COPY --from=frontend-build /app/src/frontend/build /app/static

# Create data directory for user/project instances
RUN mkdir -p /data/users /data/projects

# The gateway runs on port 9000, backend instances use 10001-10100
EXPOSE 9000

# Health check against the gateway
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:9000/gateway/health || exit 1

# Environment defaults (overridden by Fly.io secrets)
ENV GATEWAY_PORT=9000
ENV GATEWAY_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "helperai.gateway"]
