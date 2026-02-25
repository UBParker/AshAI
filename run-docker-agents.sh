#!/bin/bash

echo "🚀 AshAI Docker Agent System"
echo "================================"
echo "ALL agents run in Docker containers using your Claude subscription!"
echo "Cost: $20/month total (saving you $580+/month)"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✅ Docker is running"

# Build the Claude CLI image if it doesn't exist
if ! docker image inspect ashai-claude-cli > /dev/null 2>&1; then
    echo "📦 Building Claude CLI Docker image..."
    echo "This is a lightweight image (only 525MB)..."
    docker build -f Dockerfile.consolidated-claude-cli -t ashai-claude-cli .
    if [ $? -ne 0 ]; then
        echo "❌ Failed to build Docker image"
        exit 1
    fi
    echo "✅ Successfully built Claude CLI Docker image"
else
    echo "✅ Claude CLI Docker image exists"
fi

# Install docker Python package if needed
echo "📦 Installing Python dependencies..."
pip3 install docker aiohttp

# Kill any existing AshAI processes
echo "🔄 Stopping any existing AshAI instances..."
pkill -f "python.*helperai" || true

# Start AshAI with Docker provider
echo ""
echo "🎉 Starting AshAI with Docker-based agents!"
echo "Each agent will spawn its own Claude Code container."
echo ""

export HELPERAI_DEFAULT_PROVIDER=claude_docker
export HELPERAI_CLAUDE_CODE_ENABLED=true

# Run AshAI
python3 -m helperai