.PHONY: dev test backend frontend backend-test frontend-test down build

# Start both services with Docker Compose.
dev:
	docker compose up --build

# Stop and remove the Compose stack.
down:
	docker compose down

build:
	docker compose build

# Run every test suite.
test: backend-test frontend-test

backend-test:
	cd backend && python -m pytest

frontend-test:
	cd frontend && npm run lint && npm run typecheck

# Run the backend on its own (http://localhost:8000).
backend:
	cd backend && uvicorn app.main:app --reload --port 8000

# Run the frontend on its own (http://localhost:3000).
frontend:
	cd frontend && npm run dev
