# DriftKing

**See what changed in your infrastructure.**

DriftKing is a visual Terraform drift and change explorer. It takes structured
Terraform plan output and turns it into a clear **Before → Change → After**
picture of your infrastructure.

## The problem

`terraform plan` is correct, complete, and very hard to read.

A plan for a non-trivial stack is hundreds of lines of `~`, `+`, `-` and
`-/+` markers, deeply nested attribute diffs, and unknown-after-apply
placeholders. Reviewers have to hold the whole dependency graph in their head
to answer the questions that actually matter:

- What is being replaced, and what depends on it?
- Which changes are cosmetic, and which are destructive?
- What does the infrastructure look like *after* this apply?
- Which of these changes is the one that will cause an outage?

DriftKing answers those questions visually, from the plan Terraform already
produces.

## Project status

**Early prototype.**

**Current scope: project scaffolding only.** This repository currently
contains a minimal FastAPI backend, a minimal Next.js frontend, and the
Docker/CI plumbing to run them. The plan parser, change model, graph layer and
animation engine are *not* implemented yet.

## Planned architecture

```
Terraform plan
    ↓
terraform show -json
    ↓
Change Interpreter
    ↓
Infrastructure Change Model
    ↓
Before / After Graph
    ↓
Animation
```

See [docs/architecture.md](docs/architecture.md) for more detail on each stage.

## Scope

DriftKing does not attempt to replace Terraform. Terraform remains the source
of truth for infrastructure planning. DriftKing visualizes and explains the
resulting infrastructure transition.

## Getting started

### With Docker Compose (recommended)

```bash
docker compose up --build   # or: make dev
```

- Backend: http://localhost:8000 (health check: http://localhost:8000/health)
- Frontend: http://localhost:3000

### Without Docker

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # or: make backend
```

Frontend:

```bash
cd frontend
npm install
npm run dev                                  # or: make frontend
```

## Common commands

| Command          | What it does                                  |
| ---------------- | --------------------------------------------- |
| `make dev`       | Start backend and frontend via Docker Compose |
| `make test`      | Run backend tests and frontend lint/typecheck |
| `make backend`   | Run the backend alone on port 8000            |
| `make frontend`  | Run the frontend alone on port 3000           |
| `make down`      | Stop the Compose stack                        |

## Repository layout

```
driftking/
├── backend/        FastAPI service (Python 3.12+)
├── frontend/       Next.js + TypeScript + Tailwind app
├── fixtures/       Sample Terraform plan JSON (see fixtures/README.md)
├── docs/           Architecture and design notes
└── .github/        CI workflows
```

## Engineering principles

Keep it boring. No database, cache, queue, auth layer, cloud SDK or LLM
integration is present, and none will be added until something concrete needs
it.

## License

[MIT](LICENSE)
