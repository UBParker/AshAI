.PHONY: install dev run test lint fmt frontend clean

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
