.PHONY: install dev run test lint fmt frontend clean help docker-build docker-up docker-down docker-restart reset reset-db reset-all status shell

# Default target - show help
help:
	@echo "AshAI Management Commands"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "Development:"
	@echo "  make install      - Install package"
	@echo "  make dev          - Install with dev dependencies"
	@echo "  make run          - Run backend locally"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Lint code"
	@echo "  make fmt          - Format code"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-up    - Start services"
	@echo "  make docker-down  - Stop services"
	@echo "  make docker-restart - Restart container"
	@echo ""
	@echo "Reset (soft - keeps Docker running):"
	@echo "  make reset        - Reset backend only"
	@echo "  make reset-db     - Reset with DB cleanup"
	@echo "  make reset-all    - Reset everything"
	@echo ""
	@echo "Utilities:"
	@echo "  make status       - Show service status"
	@echo "  make shell        - Shell into container"
	@echo "  make frontend-dev - Start frontend"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"

run:
	python3 -m helperai

test:
	python3 -m pytest tests/ -v

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/
	ruff check --fix src/ tests/

frontend-install:
	cd src/frontend && npm install

frontend-dev:
	cd src/frontend && npm run dev

frontend-build:
	cd src/frontend && npm run build

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Docker commands
docker-build:
	docker compose build --no-cache claude-cli

docker-up:
	docker compose up -d
	@sleep 5
	@make status

docker-down:
	docker compose down

docker-restart:
	docker compose restart
	@sleep 5
	@make status

# Soft reset commands (Docker stays running)
reset:
	@chmod +x reset-services.sh
	@./reset-services.sh --no-frontend

reset-db:
	@chmod +x reset-services.sh
	@./reset-services.sh --db --no-frontend

reset-all:
	@chmod +x reset-services.sh
	@./reset-services.sh --db

# Utility commands
status:
	@echo "📊 Service Status"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@curl -s http://localhost:8000/api/health > /dev/null 2>&1 && echo "✅ Backend API (8000)" || echo "❌ Backend API (8000)"
	@curl -s http://localhost:8081/api/status > /dev/null 2>&1 && echo "✅ CLI Controller (8081)" || echo "❌ CLI Controller (8081)"
	@curl -s http://localhost:8082/health > /dev/null 2>&1 && echo "✅ Proxy (8082)" || echo "❌ Proxy (8082)"
	@curl -s http://localhost:5173 > /dev/null 2>&1 && echo "✅ Frontend (5173)" || echo "❌ Frontend (5173)"

shell:
	docker exec -it ashai-claude-cli /bin/bash
