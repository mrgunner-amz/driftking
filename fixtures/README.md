# Fixtures

This directory will contain **real Terraform plan JSON** — the output of
`terraform show -json` — used as deterministic test input for the backend
pipeline.

It is intentionally empty for now. Fixtures will be introduced alongside the
Change Interpreter, generated from real Terraform runs. Hand-written or
invented plan JSON should not be added: the value of these fixtures is that
they reflect what Terraform actually emits.

## Why fixtures

The DriftKing pipeline is a set of pure transformations (plan JSON → change
model → neighborhood → graphs → animation events). Real fixtures let every
layer be tested deterministically without a Terraform binary, cloud
credentials or network access.

## Planned categories

| Category            | Scenario                                                                 |
| ------------------- | ------------------------------------------------------------------------ |
| `create`            | New resources added                                                      |
| `update`            | Existing resources changed in place                                      |
| `delete`            | Resources destroyed                                                      |
| `replace`           | Resources destroyed and re-created (`-/+`, including create-before-destroy) |
| `dependency-change` | Relationships between resources change (e.g. an instance moves behind a different load balancer) |
| `drift`             | Real infrastructure differs from state, captured via `resource_drift` in the plan |

Each category will likely hold several small fixtures, one scenario per file.

## Generating a fixture (next phase)

```bash
terraform plan -out=tfplan
terraform show -json tfplan > fixtures/<category>/<scenario>.json
```

## Rules for committing fixtures

- **Scrub first.** Plan JSON can include account IDs, ARNs, hostnames, IP
  ranges, tags and — depending on the provider — secret values. Review every
  file and replace anything real with placeholder values. Never commit plan
  output from a real production workspace unreviewed.
- **Never commit binary plans or state.** `tfplan` files and `*.tfstate` are
  gitignored for this reason.
- **Record provenance.** Note the Terraform version and provider versions used
  to generate each fixture; the JSON format is versioned via `format_version`.
- **Keep them small.** A fixture should exercise one scenario, with only the
  resources needed to make it meaningful.
