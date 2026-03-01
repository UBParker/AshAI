#!/bin/bash
# Soft reset script for AshAI services
# Resets backend and frontend without killing Docker container

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}                    AshAI Services Reset Script                    ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Parse arguments
RESET_DB=false
RESTART_FRONTEND=true
CLEAR_LOGS=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --db) RESET_DB=true ;;
        --no-frontend) RESTART_FRONTEND=false ;;
        --clear-logs) CLEAR_LOGS=true ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --db           Reset the database (removes all agents)"
            echo "  --no-frontend  Don't restart the frontend"
            echo "  --clear-logs   Clear Docker container logs"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Function to restart services in Docker container
restart_docker_services() {
    echo -e "${YELLOW}🔄 Restarting services in Docker container...${NC}"

    # Kill existing Python processes (backend and CLI controller)
    docker exec ashai-claude-cli sh -c "pkill -f 'python3 -m helperai' || true" 2>/dev/null
    docker exec ashai-claude-cli sh -c "pkill -f 'cli-terminal-controller.py' || true" 2>/dev/null
    docker exec ashai-claude-cli sh -c "pkill -f 'multi-provider-proxy.py' || true" 2>/dev/null

    echo -e "${GREEN}✅ Stopped existing services${NC}"
    sleep 2

    # Restart the services using the entrypoint script
    echo -e "${YELLOW}🚀 Starting services...${NC}"
    docker exec -d ashai-claude-cli sh -c "
        # Start proxy
        if [ -n \"\$ANTHROPIC_API_KEY\" ] || [ -n \"\$OPENAI_API_KEY\" ] || [ -n \"\$GEMINI_API_KEY\" ] || [ -n \"\$OLLAMA_BASE_URL\" ]; then
            echo 'Starting multi-provider proxy...'
            python3 /home/claude/multi-provider-proxy.py &
        fi

        # Start backend API
        echo 'Starting backend API...'
        cd /app
        export HELPERAI_DATABASE_URL=sqlite+aiosqlite:////app/data/helperai.db
        export HELPERAI_PLUGINS_DIR=/app/plugins
        export HELPERAI_HOST=0.0.0.0
        export HELPERAI_PORT=8000
        export HELPERAI_ANTHROPIC_BASE_URL=http://localhost:8082
        export HELPERAI_ANTHROPIC_API_KEY=proxy
        export HELPERAI_DEFAULT_PROVIDER=cli_agent
        export HELPERAI_DEFAULT_MODEL=sonnet
        export HELPERAI_EVE_PROVIDER=anthropic
        export HELPERAI_EVE_MODEL=claude-opus-4-6
        python3 -m helperai &

        # Start CLI controller
        sleep 3
        echo 'Starting CLI controller...'
        python3 /home/claude/cli-terminal-controller.py &
    "

    echo -e "${GREEN}✅ Services restart initiated${NC}"
}

# Function to reset database
reset_database() {
    echo -e "${YELLOW}🗑️  Resetting database...${NC}"
    docker exec ashai-claude-cli sh -c "rm -f /app/data/helperai.db"
    echo -e "${GREEN}✅ Database reset${NC}"
}

# Function to restart frontend
restart_frontend() {
    echo -e "${YELLOW}🎨 Restarting frontend...${NC}"

    # Kill any existing frontend processes
    pkill -f "npm run dev" 2>/dev/null || true
    pkill -f "vite dev" 2>/dev/null || true

    # Start frontend in background
    cd src/frontend
    nohup npm run dev > /tmp/frontend.log 2>&1 &

    echo -e "${GREEN}✅ Frontend restarted (pid: $!)${NC}"
    echo -e "${BLUE}   Frontend URL: http://localhost:5173${NC}"
}

# Function to clear logs
clear_logs() {
    echo -e "${YELLOW}📝 Clearing container logs...${NC}"
    docker exec ashai-claude-cli sh -c "echo '' > /var/log/messages 2>/dev/null || true"
    echo -e "${GREEN}✅ Logs cleared${NC}"
}

# Function to check service health
check_services() {
    echo -e "${YELLOW}🔍 Checking service health...${NC}"

    # Wait for services to start
    sleep 5

    # Check backend API
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend API: Running${NC}"
    else
        echo -e "${RED}❌ Backend API: Not responding${NC}"
    fi

    # Check CLI controller
    if curl -s http://localhost:8081/api/status > /dev/null 2>&1; then
        echo -e "${GREEN}✅ CLI Controller: Running${NC}"
    else
        echo -e "${RED}❌ CLI Controller: Not responding${NC}"
    fi

    # Check proxy
    if curl -s http://localhost:8082/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Multi-Provider Proxy: Running${NC}"
    else
        echo -e "${RED}❌ Multi-Provider Proxy: Not responding${NC}"
    fi

    # Check frontend
    if [ "$RESTART_FRONTEND" = true ]; then
        if curl -s http://localhost:5173 > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Frontend: Running${NC}"
        else
            echo -e "${RED}❌ Frontend: Not responding${NC}"
        fi
    fi
}

# Function to show agents
show_agents() {
    echo -e "${YELLOW}🤖 Current agents:${NC}"
    curl -s http://localhost:8000/api/agents 2>/dev/null | python3 -c "
import json, sys
try:
    agents = json.load(sys.stdin)
    if not agents:
        print('   No agents found')
    else:
        for a in agents:
            status = '✅' if a['status'] == 'idle' else '❌' if a['status'] == 'error' else '🔄'
            print(f\"   {status} {a['name']}: {a['model_name']} via {a['provider_name']} ({a['status']})\")
except:
    print('   Could not fetch agents')
" || echo "   Could not fetch agents"
}

# Main execution
echo -e "${YELLOW}📋 Configuration:${NC}"
echo -e "   Reset database: $RESET_DB"
echo -e "   Restart frontend: $RESTART_FRONTEND"
echo -e "   Clear logs: $CLEAR_LOGS"
echo

# Execute operations
if [ "$RESET_DB" = true ]; then
    reset_database
fi

restart_docker_services

if [ "$RESTART_FRONTEND" = true ]; then
    restart_frontend
fi

if [ "$CLEAR_LOGS" = true ]; then
    clear_logs
fi

# Check service health
check_services

# Show agents
echo
show_agents

echo
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}                        Reset Complete!                            ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"