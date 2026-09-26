# Architecture

> **Status: planned.** Only the scaffolding (a FastAPI service with
> `GET /health` and a static Next.js page) exists today. This document
> describes the architecture we intend to build, so that early decisions stay
> compatible with it. Nothing below is a claim about implemented behavior.

## Overview

```
terraform plan -out=tfplan               (user's environment)
          │
          ▼
terraform show -json tfplan              (user's environment)
          │
══════════╪═══════════════════════════════  DriftKing boundary
          ▼
┌─────────────────────────────┐
│ 1. Terraform Input          │  backend
├─────────────────────────────┤
│ 2. Change Interpreter       │  backend
├─────────────────────────────┤
│ 3. Infrastructure Change    │  backend   ◄── the frontend's only contract
│    Model                    │
├─────────────────────────────┤
│ 4. Change Neighborhood      │  backend
├─────────────────────────────┤
│ 5. Visualization            │  backend: graphs + animation events
│                             │  frontend: rendering
└─────────────────────────────┘
          ┆
┌─────────────────────────────┐
│ 6. AI Interpretation        │  future, optional, never authoritative
└─────────────────────────────┘
```

Layers 1–5 are deterministic transformations. Each consumes the output of the
layer above it and can be tested in isolation from fixture files, with no
Terraform binary, cloud credentials or network access in the test path.

## Guiding principle

**Terraform remains the source of truth.** DriftKing visualizes Terraform's
planned transition. It does not re-derive, second-guess or reconcile that plan,
and it never runs Terraform itself. If DriftKing and Terraform ever disagree,
DriftKing is wrong.

## Layers

### 1. Terraform Input

The user runs, in their own environment:

```bash
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
```

`plan.json` — Terraform's documented
[JSON output format](https://developer.hashicorp.com/terraform/internals/json-format) —
is DriftKing's only input. Consuming the structured, versioned format rather
than scraping human-readable plan text is what makes the rest of the pipeline
tractable.

Responsibilities:

- Accept plan JSON and validate that it is structurally a plan.
- Check `format_version` and fail explicitly on versions we do not understand,
  rather than guessing.
- Parse into typed (Pydantic) structures that mirror Terraform's schema.

This layer knows about Terraform's schema and nothing else.

### 2. Change Interpreter

Converts Terraform's representation into DriftKing's. This is the **only**
layer that should know both vocabularies.

Expected responsibilities:

- Map `resource_changes[].change.actions` to lifecycle actions. Terraform
  expresses a replacement as an ordered pair of actions
  (`["delete", "create"]` or `["create", "delete"]`); DriftKing should
  represent that as a single *replace* of one resource, not two unrelated
  events.
- Surface *why* a replacement happens (`replace_paths`) and the attribute-level
  differences between `before` and `after`.
- Represent values Terraform does not know yet (`after_unknown`) honestly, as
  unknown — never as empty or null.
- Respect sensitivity markers (`before_sensitive` / `after_sensitive`) so that
  sensitive values are never forwarded to the frontend.
- Extract relationships from the plan's `configuration` section (references
  and `depends_on`). How complete those relationships can be from plan JSON
  alone is an open question for the next phase.

### 3. Infrastructure Change Model

DriftKing's own typed representation of an infrastructure transition. It is
the contract between the backend pipeline and everything downstream, including
the frontend.

Expected to represent:

| Concept           | Notes                                                                |
| ----------------- | -------------------------------------------------------------------- |
| Resources         | Every resource relevant to the change                                |
| Resource identity | Stable across before/after — see constraint D                        |
| Resource type     | e.g. `aws_instance`, plus provider and module path                   |
| Lifecycle action  | created, destroyed, updated, replaced, unchanged                     |
| Before state      | Attribute values prior to the change (absent for creates)            |
| After state       | Attribute values after the change (absent for deletes; may be unknown) |
| Relationships     | Directed edges between resources, with their own before/after status |
| Change metadata   | e.g. which attributes force replacement, sensitivity, drift vs. plan |

**Not implemented yet.** The concrete schema will be designed in the next
phase against real plan JSON, not guessed at here.

### 4. Change Neighborhood

Real infrastructure can contain thousands of resources; a plan usually touches
a handful. Rendering everything buries the change.

The Change Neighborhood selects what deserves to be on screen:

```
changed resources
  + relevant relationships
  + enough surrounding context to make the change legible
```

For the example of adding `API-03` behind a load balancer, the neighborhood is
the new instance, the load balancer it attaches to, the database it connects
to, and its sibling instances — not the VPC's other 400 resources.

The selection must be deterministic: the same model always yields the same
neighborhood.

### 5. Visualization

Converts the neighborhood into:

- a **before graph** — the neighborhood as it is,
- an **after graph** — the neighborhood as it will be,
- an ordered list of **animation events** that transform one into the other
  (e.g. *node created*, *node destroyed*, *node replaced*, *node updated*,
  *edge added*, *edge removed*).

Graph construction and event generation belong in the backend, where they can
be unit-tested. The frontend's job is rendering: it plays events it is given.
Layout and rendering technology (SVG first; any library only once the real
graph requirements are understood) are frontend concerns.

### 6. AI Interpretation (future only)

A possible later layer that explains *why a change matters* — for example,
that replacing a database instance implies downtime.

Rules for that layer, if it is ever built:

- It consumes the Infrastructure Change Model's facts. It does not read raw
  plan JSON and it does not produce facts.
- AI is **never** the source of infrastructure truth. Every statement it makes
  must be traceable to a deterministic fact from layers 1–5.
- The product must be fully useful with this layer switched off.

## Design constraints

These shape decisions made now, even though the layers above do not exist yet.

**A. Terraform is not the UI model.** The frontend receives DriftKing's Change
Model, never raw Terraform JSON. Frontend components must not depend on
Terraform's structure, so that changes in Terraform's format stay contained in
the backend.

**B. Terraform parsing belongs in the backend.** The frontend never parses
plan JSON. There is exactly one parser, and it is tested in Python.

**C. Animation is deterministic.** The same Change Model always produces the
same logical animation: same events, same order. No randomness, no reliance on
dictionary or set iteration order, no wall-clock input. This makes animations
reproducible, snapshot-testable and debuggable.

**D. Resource identity matters.** A resource present in both BEFORE and AFTER
keeps one identity. `aws_instance.api[0]` whose attributes changed is the same
object being *updated* — it must not appear to be destroyed and re-created.
Terraform's full resource address (module path + type + name + index key) is
the natural starting point for identity; a *replaced* resource keeps its
identity while its underlying object is swapped.

**E. Don't visualize the entire world by default.** Design around the change
neighborhood, not full-estate rendering. Performance goals should target
dozens of nodes, not thousands.

**F. Facts before AI.** The deterministic layers must be able to state, on
their own:

- resource created
- resource destroyed
- resource updated
- resource replaced
- relationship changed

before any AI is introduced. AI interprets those facts; it never replaces them.

## Component responsibilities

| Component   | Stack                                  | Owns                                          |
| ----------- | -------------------------------------- | --------------------------------------------- |
| `backend/`  | Python 3.12+, FastAPI, Pydantic        | Layers 1–5 (input → graphs and events)        |
| `frontend/` | Next.js, TypeScript, React, Tailwind   | Rendering and playing back animation events   |
| `fixtures/` | Real, scrubbed `terraform show -json`  | The ground truth that the pipeline is tested against |

## Deliberately absent

No database, cache, message queue, authentication, user accounts, cloud SDK,
GitHub integration, LLM integration or background worker. Plan JSON is
self-contained and small enough to process within a single request. Each of
those will be added only when a concrete requirement forces it.
