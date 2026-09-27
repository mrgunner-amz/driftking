# Fixtures

Real Terraform plan JSON — the output of `terraform show -json` — used as
deterministic input for the backend tests and bundled in the app.

Nothing here is hand-written. Every plan is produced by
[`terraform/generate.sh`](terraform/generate.sh) from the configurations
under [`terraform/app-stack/`](terraform/app-stack), which use only
Terraform's built-in `terraform_data` resource. No cloud provider, credentials
or provider downloads are involved.

## Plans

| File                                | Scenario                                                  |
| ----------------------------------- | --------------------------------------------------------- |
| `plans/app-stack-initial.json`      | Empty state → v1. Everything is created.                  |
| `plans/app-stack-upgrade.json`      | v1 → v2. The mixed scenario below.                        |
| `plans/app-stack-no-changes.json`   | v1 → v1. Terraform plans no changes.                      |

`app-stack-upgrade` covers, in one real plan:

| Category            | What Terraform plans                                                    |
| ------------------- | ----------------------------------------------------------------------- |
| create              | `terraform_data.cache`, `terraform_data.api[2]` (count 2 → 3)           |
| update              | `api[0]`, `api[1]`, `load_balancer` (IDs they reference become unknown) |
| delete              | `terraform_data.legacy_worker` (removed from configuration)            |
| replace             | `terraform_data.database` (`triggers_replace` engine 15 → 16)           |
| dependency-change   | new edges to `cache` and `api[2]`; `legacy_worker`'s edge goes away     |
| module              | `module.monitoring.terraform_data.health_check`, linked via `var.*`     |
| sensitive / unknown | `var.db_password` (sensitive), IDs known only after apply               |

Not yet covered: **drift**. `terraform_data` has no remote object that can
change outside Terraform, so a real drift fixture needs a provider whose
infrastructure can be modified independently.

## Regenerating

```bash
make fixtures          # or: fixtures/terraform/generate.sh
```

Requires `terraform` ≥ 1.4 and `python3`. The script works in a temporary
directory, runs `terraform apply` against a throwaway local state to create
the "before" side (terraform_data manages no real infrastructure), and copies
back only the `show -json` output, re-indented for readable diffs. The
committed plans were generated with Terraform 1.16.4. Plan output includes
generated IDs and a timestamp, so regenerating produces a diff.

## Rules for adding fixtures

- **Generate, don't write.** Fixtures must come from a real Terraform run.
  Tests may derive edge cases by mutating copies of real fixtures in memory.
- **Scrub first.** Plan JSON contains sensitive values in clear text, plus
  account IDs, ARNs, hostnames and tags. The only "secret" here is the
  placeholder `example-not-a-real-secret`. Never commit plan output from a real
  workspace unreviewed.
- **Never commit binary plans, state or `.terraform/`.** They are gitignored.
- **Record provenance**: Terraform version and scenario, as above.
