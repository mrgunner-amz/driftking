# Architecture

> Status: **planned**. Nothing below the scaffolding layer is implemented yet.
> This document describes the shape we are building toward, so that the
> scaffolding stays clean enough to grow into it.

## Pipeline

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

Each stage is a pure transformation of the stage above it. That matters: it
keeps every layer independently testable from fixture files, with no Terraform
binary, cloud credentials or network access in the test path.

### 1. Terraform plan

The user runs `terraform plan -out=plan.tfplan` in their own environment.
DriftKing never runs Terraform, never touches state, and never holds cloud
credentials. Terraform remains the source of truth.

### 2. `terraform show -json`

The user converts the binary plan to Terraform's documented JSON plan
representation:

```bash
terraform show -json plan.tfplan > plan.json
```

That JSON is DriftKing's only input. Consuming a stable, documented format —
rather than scraping human-readable plan text — is what makes the rest of the
pipeline tractable.

Sample plan JSON for development and tests lives in [`fixtures/`](../fixtures).

### 3. Change Interpreter

Parses and validates the plan JSON into typed structures, then interprets it:

- Reads `resource_changes[]` and classifies each `change.actions` entry
  (`no-op`, `create`, `update`, `delete`, `replace`).
- Distinguishes a replace from an in-place update, and identifies the
  attribute that forces it.
- Resolves `unknown_after_apply` values into a form the UI can render honestly
  rather than pretending to know them.
- Extracts resource addresses, module paths, provider and type.

This layer is deliberately dumb about *meaning*: it normalizes, it does not
rank or explain.

### 4. Infrastructure Change Model

DriftKing's own internal representation, independent of Terraform's schema.
Roughly: a set of resources, each with a before state, an after state, a
change kind, and edges to the resources it depends on.

Keeping this separate from the Terraform JSON is the central design decision.
It gives us one place to add blast-radius scoring, severity, and grouping, and
it leaves room to support other plan sources later without rewriting the UI.

### 5. Before / After Graph

Two graph snapshots derived from the change model — infrastructure as it is,
and as it will be — plus the correspondence between their nodes. Layout is
computed on top of this so that unchanged resources stay put between the two
snapshots and changed ones are the things that move.

### 6. Animation

The frontend renders the transition between the two graph snapshots: nodes
appearing, being removed, being replaced, or changing in place. The goal is
that a reviewer sees the destructive change before they read a single line of
the plan.

## Component layout

| Component  | Stack                                   | Responsibility                                   |
| ---------- | --------------------------------------- | ------------------------------------------------ |
| `backend/` | Python 3.12+, FastAPI, Pydantic         | Stages 3–5: parse, interpret, model, build graphs |
| `frontend/`| Next.js, TypeScript, React, Tailwind    | Stage 6: render and animate the transition        |

The backend exposes JSON over HTTP; the frontend is a pure consumer of that
API. Today the only endpoint is `GET /health`.

## Non-goals

- **Replacing Terraform.** DriftKing visualizes and explains a transition
  Terraform has already planned.
- **Running Terraform.** No Terraform binary, no state access, no cloud
  credentials.
- **Applying changes.** DriftKing is read-only by design.

## Deliberately absent

No database, cache, message queue, authentication layer, cloud SDK, LLM
integration, vector store or background worker is present. The plan JSON is
self-contained and small enough to process in a request, so none of that is
needed yet. Each will be added only when a concrete requirement forces it.
