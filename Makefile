.PHONY: setup dev-api dev-api-watch dev-dashboard refine verify-backend check check-python check-dashboard up down migrate seed-flights

# Use the checkout's uv installation for worker verification and reload subprocesses.
export PATH := $(CURDIR)/.tools/bin:$(PATH)
UV := $(if $(wildcard $(CURDIR)/.tools/bin/uv),$(CURDIR)/.tools/bin/uv,uv)

setup:
	$(UV) sync --all-packages --frozen
	npm --prefix apps/dashboard ci

# Check for an existing listener before starting either development server.
dev-api:
	@if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then echo "Port 8000 already has a listener; inspect it before starting another API."; exit 1; fi
	$(UV) run --package airline-api uvicorn airline_api.main:app --host 127.0.0.1 --port 8000

# Interactive editing only. The refinement worker refuses a watched service.
dev-api-watch:
	@if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then echo "Port 8000 already has a listener; inspect it before starting another API."; exit 1; fi
	$(UV) run --package airline-api uvicorn airline_api.main:app --reload --host 127.0.0.1 --port 8000

dev-dashboard:
	@if lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then echo "Port 3000 already has a listener; inspect it before starting another dashboard."; exit 1; fi
	npm --prefix apps/dashboard run dev -- --hostname 127.0.0.1 --port 3000

refine:
	$(UV) run --package airline-refiner airline-refiner run

verify-backend:
	$(UV) run --all-packages python -m airline_refiner.verification

check: check-python check-dashboard

check-python:
	$(UV) run --all-packages ruff check .
	$(UV) run --all-packages ruff format --check .
	$(UV) run --all-packages mypy
	$(UV) run --all-packages pytest

check-dashboard:
	npm --prefix apps/dashboard run lint
	npm --prefix apps/dashboard run format:check
	npm --prefix apps/dashboard run typecheck
	npm --prefix apps/dashboard test
	npm --prefix apps/dashboard run build

up:
	docker compose up --build

down:
	docker compose down

migrate:
	$(UV) run --package airline-api alembic -c apps/api/alembic.ini upgrade head

seed-flights:
	$(UV) run --package airline-api airline-seed-flights
