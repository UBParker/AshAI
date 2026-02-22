# AshAI — single container serving both gateway (API) and frontend (static SPA).
# The gateway spawns per-user/project backend subprocesses with their own SQLite DBs.

# --- Stage 1: Build frontend ---
FROM node:20-slim AS frontend-build

WORKDIR /app/src/frontend

COPY src/frontend/package.json src/frontend/package-lock.json* ./
RUN npm install

COPY src/frontend/ ./

# Frontend env vars baked in at build time (anon key is public, safe to embed)
ENV VITE_SUPABASE_URL=https://mjosrqijnvjtkywadbxm.supabase.co
ENV VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1qb3NycWlqbnZqdGt5d2FkYnhtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE2MzYyNjEsImV4cCI6MjA4NzIxMjI2MX0.N6j-2ND2XS8w5l_cXbabXTX26KMI4So7q1UAIHz-Ko4
ENV VITE_GATEWAY_URL=

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
