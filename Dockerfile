# AshAI Gateway — runs the multi-user gateway service that spawns per-user backend instances.
# Each user/project gets its own subprocess with its own SQLite DB under /data/.

FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[gateway]"

# Copy source code
COPY src/ ./src/
COPY .env.example ./

# Install the package
RUN pip install --no-cache-dir -e .

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
