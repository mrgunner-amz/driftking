# DriftKing

A visual explorer for Terraform infrastructure changes and drift.

> **Current status: early prototype — V1 vertical slice.**
> DriftKing can read a real `terraform show -json` plan and show BEFORE →
> AFTER as an animated graph with a change summary. It is a first milestone to
> judge whether visualizing a plan beats reading it, not a finished tool.
> Drift visualization does not exist yet.

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

The transition between the two is animated. The animation is not the point;
the point is *"I immediately understand what changed in my infrastructure."*
The animation makes that understanding tangible.

## What V1 does

1. Reads a plan: one of the bundled [real fixtures](fixtures/README.md), or
   your own `plan.json` via **Open plan JSON…**.
2. Interprets `resource_changes[].change.actions` into create, update,
   replace (one resource, two states), delete and no-op, with attribute-level
   changes where unknown values stay unknown and sensitive values are never
   sent to the browser.
3. Derives dependencies from the plan's configuration and keeps the changed
   resources plus their direct neighbors.
4. Draws BEFORE and AFTER as **one** graph with fixed positions, and animates
   between them: destroyed nodes fade, updated nodes change state in place,
   replaced nodes swap old for new in the same slot, created nodes grow in,
   and edges draw or retract.
5. Lists what changed, grouped by consequence, with Terraform addresses and
   the attributes behind each change.

Known limitations are listed [below](#known-limitations).

## Architecture

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
frontend only receives DriftKing's own [Change Model](docs/change-model.md),
never raw Terraform JSON, and decides on its own how to lay out and animate it.
See [docs/architecture.md](docs/architecture.md) for each layer and the design
constraints behind them.

### API

| Method | Path                    | Returns                                            |
| ------ | ----------------------- | -------------------------------------------------- |
| GET    | `/health`               | `{"status": "ok"}`                                 |
| GET    | `/api/fixtures`         | Names of the bundled plan fixtures                 |
| GET    | `/api/fixtures/{name}`  | The Change Model for that fixture                  |
| POST   | `/api/plans`            | The Change Model for a `terraform show -json` body (≤ 10 MiB) |

Plans DriftKing cannot represent faithfully return `422` with the reason,
rather than a best guess. The API is read-only and never runs Terraform.

## Important architectural principle

> Terraform remains the source of truth.
> DriftKing visualizes Terraform's planned transition rather than implementing
> its own Terraform reconciliation engine.

DriftKing never runs Terraform, never reads state directly, and never holds
cloud credentials. Its input is the JSON that `terraform show -json` produces
from a plan you created yourself.

## Future capabilities

These are **future work** and are **not implemented**:

- Terraform drift visualization
- Infrastructure change history
- AI-assisted explanation of changes (interpreting deterministic facts, never
  replacing them)

## Repository layout

```
driftking/
├── backend/            FastAPI service (Python 3.12+)
│   ├── app/            Parser (terraform_plan, interpreter, values,
│   │                   relationships), Change Model, API
│   └── tests/
├── frontend/           Next.js + TypeScript + Tailwind CSS
│   ├── app/            App Router page and styles (incl. animation CSS)
│   ├── components/     Explorer, ChangeGraph, ChangeSummary
│   └── lib/            Change Model types, layout, presentation helpers
├── fixtures/
│   ├── plans/          Real `terraform show -json` output
│   └── terraform/      The configs and script that generate them
├── docs/               Architecture and Change Model notes
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

Open http://localhost:3000. The bundled `app-stack-upgrade` plan loads and
plays its BEFORE → AFTER transition.

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
| `make test`     | Run the backend (pytest) and frontend (Vitest) test suites       |
| `make lint`     | Ruff lint + format check, mypy, ESLint and the TypeScript check  |
| `make format`   | Auto-format and auto-fix backend code with Ruff                  |
| `make check`    | Everything CI runs: `lint`, `test` and a frontend production build |
| `make fixtures` | Regenerate `fixtures/plans` from real Terraform runs             |
| `make clean`    | Remove local dependencies, caches and build output               |

Local targets install their dependencies on first use, so `make test` or
`make lint` work on a fresh clone.

## Known limitations

V1 is intentionally small. In particular:

- **Relationships are partial.** They come from the planned configuration.
  Terraform does not record the previous configuration, so an edge between two
  resources that exist on both sides cannot be shown as new or removed; it is
  drawn in both states and the UI says so. References through `local.*` are
  not followed.
- **Neighborhood is one hop.** Changed resources plus directly connected ones.
- **Not supported yet** (reported as a clear error, not approximated):
  deposed objects, `forget` actions, plan `format_version` other than 1.x.
  Drift that Terraform reports is counted but not drawn. Data sources are
  left out.
- **Scale.** The layout is built for tens of nodes. Large plans will render,
  but densely.
- **Only tested against `terraform_data` plans.** Real provider resources use
  the same plan format, but no real-provider fixture has been checked yet.

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
