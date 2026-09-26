# DriftKing developer commands. Run `make help` for the list.
#
# Local (non-Docker) targets use a virtualenv at backend/.venv and
# frontend/node_modules; both are created on first use. Override the
# interpreter with e.g. `make PYTHON=python3.13 install`.

PYTHON ?= python3
VENV   := $(CURDIR)/backend/.venv
BIN    := $(VENV)/bin

BACKEND_STAMP  := $(VENV)/.installed
FRONTEND_STAMP := frontend/node_modules/.package-lock.json

.DEFAULT_GOAL := help

.PHONY: help dev down install install-backend install-frontend test lint format check \
        backend frontend backend-lint frontend-lint frontend-build clean

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# --- Docker ---------------------------------------------------------------

dev: ## Start backend (:8000) and frontend (:3000) with Docker Compose
	docker compose up --build

down: ## Stop the Docker Compose stack
	docker compose down

# --- Dependencies -----------------------------------------------------------

install: install-backend install-frontend ## Install local backend and frontend dependencies

install-backend: $(BACKEND_STAMP)

install-frontend: $(FRONTEND_STAMP)

$(BACKEND_STAMP): backend/requirements.txt backend/requirements-dev.txt
	@$(PYTHON) -c 'import sys; sys.exit(sys.version_info < (3, 12))' \
		|| { echo "error: $(PYTHON) is older than 3.12; run e.g. 'make PYTHON=python3.12 install'" >&2; exit 1; }
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --quiet --upgrade pip
	$(BIN)/pip install --quiet -r backend/requirements-dev.txt
	@touch $@

$(FRONTEND_STAMP): frontend/package.json frontend/package-lock.json
	cd frontend && npm ci

# --- Quality ---------------------------------------------------------------

test: $(BACKEND_STAMP) ## Run the backend test suite
	cd backend && $(BIN)/pytest

lint: backend-lint frontend-lint ## Run all linters and type checkers

backend-lint: $(BACKEND_STAMP)
	cd backend && $(BIN)/ruff check .
	cd backend && $(BIN)/ruff format --check .
	cd backend && $(BIN)/mypy

frontend-lint: $(FRONTEND_STAMP)
	cd frontend && npm run lint
	cd frontend && npm run typecheck

frontend-build: $(FRONTEND_STAMP)
	cd frontend && npm run build

format: $(BACKEND_STAMP) ## Auto-format and auto-fix backend code
	cd backend && $(BIN)/ruff format .
	cd backend && $(BIN)/ruff check --fix .

check: lint test frontend-build ## Everything CI runs

# --- Run locally without Docker -------------------------------------------

backend: $(BACKEND_STAMP) ## Run the backend locally on :8000 with reload
	cd backend && $(BIN)/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend: $(FRONTEND_STAMP) ## Run the frontend locally on :3000
	cd frontend && npm run dev

clean: ## Remove local dependencies and build output
	rm -rf $(VENV) frontend/node_modules frontend/.next frontend/next-env.d.ts
	find backend -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
