# DriftKing

A visual explorer for Terraform infrastructure changes and drift.

> **Current status: Early prototype — project scaffolding only.**
> Nothing described below as "planned" or "future" exists yet. There is no
> Terraform parsing, no visualization and no drift analysis in this repository
> today.

## Problem

Terraform plans are precise. They are also cognitively expensive to read.

```
Plan: 3 to add, 5 to change, 1 to destroy.
```

Behind that summary line is a long textual diff of `+`, `~`, `-` and `-/+`
markers, nested attribute changes and `(known after apply)` placeholders. To
understand what is actually happening, an engineer has to reconstruct the
resource graph in their head: what is being replaced, what depends on it, and
what the infrastructure looks like once the apply finishes.

That gets harder as the number of resources and relationships grows, and it
does not get easier when the question is being asked of an AI coding
assistant — *"What changed here?"*, *"Is this drift safe?"*, *"Why is Terraform
trying to replace this?"* — because the answer is only as trustworthy as the
facts it is built on.

## Product idea

> Terraform tells us what is changing.
> DriftKing makes the transition understandable.

The goal is to turn a plan into a **Before → Change → After** view of the
affected infrastructure:

```
BEFORE                              AFTER

     Load Balancer                       Load Balancer
          |                                   |
    +-----+-----+                   +---------+---------+
    |           |                   |         |         |
  API-01      API-02              API-01    API-02    API-03   (+ created)
    |           |                   |         |         |
    +-----+-----+                   +---------+---------+
          |                                   |
          DB                                  DB
```

The transition between the two will be animated. The animation is not the
point; the point is *"I immediately understand what changed in my
infrastructure."* The animation makes that understanding tangible.

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
Change Neighborhood
      ↓
Before / After Graph
      ↓
Animation
```

Terraform parsing and change interpretation happen in the Python backend. The
frontend will only ever receive DriftKing's own Change Model, never raw
Terraform JSON. See [docs/architecture.md](docs/architecture.md) for what each
layer is responsible for and the design constraints behind them.

## Important architectural principle

> Terraform remains the source of truth.
> DriftKing visualizes Terraform's planned transition rather than implementing
> its own Terraform reconciliation engine.

DriftKing never runs Terraform, never reads state directly, and never holds
cloud credentials. Its input is the JSON that `terraform show -json` produces
from a plan you created yourself.

## Future capabilities

These are **future work** and are **not implemented**:

- Terraform plan visualization
- Terraform drift visualization
- Infrastructure change history
- AI-assisted explanation of changes (interpreting deterministic facts, never
  replacing them)

## Repository layout

```
driftking/
├── backend/            FastAPI service (Python 3.12+)
│   ├── app/            Application package — currently just GET /health
│   └── tests/
├── frontend/           Next.js + TypeScript + Tailwind CSS
│   └── app/            App Router pages
├── fixtures/           Future home of real Terraform plan JSON fixtures
├── docs/               Architecture notes
└── .github/workflows/  CI
```

## Getting started

### Prerequisites

- Docker with Docker Compose, **or**
- Python 3.12+, Node.js 20.9+ and `make` for running without Docker

### Run with Docker

```bash
make dev            # equivalent to: docker compose up --build
```

| Service  | URL                          |
| -------- | ---------------------------- |
| Frontend | http://localhost:3000        |
| Backend  | http://localhost:8000        |
| Health   | http://localhost:8000/health |
| API docs | http://localhost:8000/docs   |

### Run without Docker

```bash
make install        # backend/.venv + frontend/node_modules
make backend        # terminal 1 — http://localhost:8000
make frontend       # terminal 2 — http://localhost:3000
```

If your default `python3` is older than 3.12, pass the interpreter explicitly:
`make PYTHON=python3.12 install`.

## Make commands

| Command         | What it does                                                     |
| --------------- | ---------------------------------------------------------------- |
| `make help`     | List all commands                                                |
| `make dev`      | Start backend and frontend with Docker Compose                   |
| `make down`     | Stop the Docker Compose stack                                    |
| `make install`  | Install local backend and frontend dependencies                  |
| `make backend`  | Run the backend locally on port 8000 with auto-reload            |
| `make frontend` | Run the frontend locally on port 3000                            |
| `make test`     | Run the backend test suite (pytest)                              |
| `make lint`     | Ruff lint + format check, mypy, ESLint and the TypeScript check  |
| `make format`   | Auto-format and auto-fix backend code with Ruff                  |
| `make check`    | Everything CI runs: `lint`, `test` and a frontend production build |
| `make clean`    | Remove local dependencies, caches and build output               |

Local targets install their dependencies on first use, so `make test` or
`make lint` work on a fresh clone.

## Engineering principles

- **Facts before interpretation.** The deterministic pipeline must be able to
  state *created, destroyed, updated, replaced, relationship changed* before
  any AI layer is introduced.
- **Deterministic output.** The same plan produces the same model, the same
  graph and the same animation.
- **Minimal dependencies.** No database, cache, queue, auth, cloud SDK or LLM
  integration until something concrete requires it.

## License

[MIT](LICENSE)
