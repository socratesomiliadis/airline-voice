.PHONY: setup dev-api dev-dashboard check check-python check-dashboard up down migrate

setup:
	uv sync --all-packages --frozen
	npm --prefix apps/dashboard ci

# Check for an existing listener before starting either development server.
dev-api:
	@if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then echo "Port 8000 already has a listener; inspect it before starting another API."; exit 1; fi
	uv run --package airline-api uvicorn airline_api.main:app --reload --host 127.0.0.1 --port 8000

dev-dashboard:
	@if lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then echo "Port 3000 already has a listener; inspect it before starting another dashboard."; exit 1; fi
	npm --prefix apps/dashboard run dev -- --hostname 127.0.0.1 --port 3000

check: check-python check-dashboard

check-python:
	uv run --all-packages ruff check .
	uv run --all-packages ruff format --check .
	uv run --all-packages mypy
	uv run --all-packages pytest

check-dashboard:
	npm --prefix apps/dashboard run lint
	npm --prefix apps/dashboard run format:check
	npm --prefix apps/dashboard run typecheck
	npm --prefix apps/dashboard run build

up:
	docker compose up --build

down:
	docker compose down

migrate:
	uv run --package airline-api alembic -c apps/api/alembic.ini upgrade head
