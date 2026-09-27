# Architecture

> **Status: V1 vertical slice.** Layers 1–5 exist in a first, deliberately
> small form: a plan-JSON parser, the Change Model, a one-hop neighborhood,
> and a frontend that renders and animates BEFORE → AFTER. Layer 6 (AI) does
> not exist. Sections below say what V1 does and where it stops.

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
└─────────────────────────────┘
          │  JSON over HTTP (GET /api/fixtures/{name}, POST /api/plans)
          ▼
┌─────────────────────────────┐
│ 5. Visualization            │  frontend: layout, BEFORE/AFTER, animation
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
  and `depends_on`, following `var.*` into module calls and module outputs
  back to resources).

**What V1 learned about relationships.** `prior_state` looks like it should
describe the BEFORE graph, but it does not: Terraform records dependencies
there as a *transitive closure*, and refreshes them against the *new*
configuration during planning (in the fixture, `api[0]` "already" depends on
a cache that does not exist yet). The plan does not contain the previous
configuration at all. So V1 only claims what can be proven:

| Edge                                        | Status    | Source                                   |
| ------------------------------------------- | --------- | ---------------------------------------- |
| an endpoint is created                      | `added`   | configuration                            |
| an endpoint is destroyed                    | `removed` | configuration, or `prior_state` reduced to non-implied edges when the resource has no configuration left |
| both endpoints exist before and after       | `present` | configuration; drawn on both sides, and the UI says it cannot be verified as old or new |

References through `local.*` are not followed (Terraform does not export
local values' expressions), so such dependencies are missing rather than
guessed.

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

V1's concrete schema is documented in [change-model.md](change-model.md).
Rather than shipping raw before/after objects, each resource carries a list of
changed leaf attributes, each side typed as `known`, `unknown`, `sensitive` or
`absent`.

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

**V1:** changed resources plus every resource sharing an edge with one of
them (one hop). Everything else is counted in `hidden_unchanged` and left out
of the response.

### 5. Visualization

Owned by the frontend. The backend describes *what* changed; how that is
shown and animated is a presentation decision, so no layout or animation
instructions cross the API.

V1 (`frontend/lib/layout.ts`, `frontend/components/ChangeGraph.tsx`):

- **One layout for both states.** A deterministic layered layout is computed
  over the union of BEFORE and AFTER, dependents above dependencies. Each
  resource gets one slot, so the transition transforms a single graph instead
  of switching diagrams. Created resources grow into slots that are empty in
  BEFORE; destroyed ones leave a labelled outline in AFTER.
- **Animation vocabulary**, played in three stages (reversed when going back):
  1. *destroy* — node fades and shrinks; its edges turn red and retract
  2. *update* — node stays put, pulses once and turns amber;
     *replace* — the old card lifts out and the new card settles into the
     same slot (one resource, two states)
  3. *create* — node grows in; new edges draw toward their target
- The choreography is CSS transitions keyed on the SVG's `data-phase`, so the
  same model always plays the same animation. `prefers-reduced-motion` turns
  it into an instant switch.
- Plain SVG. No graph or animation library was needed at this size.

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

These shaped the V1 implementation and remain binding.

**A. Terraform is not the UI model.** The frontend receives DriftKing's Change
Model, never raw Terraform JSON. Frontend components must not depend on
Terraform's structure, so that changes in Terraform's format stay contained in
the backend.

**B. Terraform parsing belongs in the backend.** The frontend never parses
plan JSON. There is exactly one parser, and it is tested in Python.

**C. Animation is deterministic.** The same Change Model always produces the
same logical animation: same stages, same order. No randomness, no reliance on
dictionary or set iteration order, no wall-clock input. The layout sorts by
address before ordering, and the frontend tests assert that BEFORE and AFTER
render identical markup apart from the phase.

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
| `backend/`  | Python 3.12+, FastAPI, Pydantic        | Layers 1–4 (plan JSON → Change Model)         |
| `frontend/` | Next.js, TypeScript, React, Tailwind   | Layer 5 (layout, BEFORE/AFTER, animation, summary) |
| `fixtures/` | Real, scrubbed `terraform show -json`  | The ground truth that the pipeline is tested against |

## Deliberately absent

No database, cache, message queue, authentication, user accounts, cloud SDK,
GitHub integration, LLM integration or background worker. Plan JSON is
self-contained and small enough to process within a single request. Each of
those will be added only when a concrete requirement forces it.
