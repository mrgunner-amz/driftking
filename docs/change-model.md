# Change Model (V1)

The Change Model is the only thing the frontend receives. It is produced by
`backend/app/interpreter.py` from `terraform show -json` output and defined in
`backend/app/change_model.py` (mirrored in `frontend/lib/changeModel.ts`).

It says **what** Terraform plans to change. It contains no layout, colors or
animation steps.

```
ChangeSet
├── terraform_version, format_version, complete
├── counts             {create, update, replace, delete, no_op}  — whole plan
├── resources[]        changed resources + direct neighbors
│   ├── address        identity (Terraform's instance address)
│   ├── module_address, type, name, index, provider_name
│   ├── action         create | update | replace | delete | no-op
│   ├── action_reason  Terraform's own reason, e.g. replace_because_cannot_update
│   ├── replace_order  delete_before_create | create_before_destroy (replace only)
│   ├── replace_paths  attribute paths Terraform says force replacement
│   ├── previous_address, importing
│   └── changes[]      one entry per changed leaf attribute
│       ├── path               ["input", "engine_version"]
│       ├── before / after     {kind: known, value} | {kind: unknown}
│       │                      | {kind: sensitive}  | {kind: absent}
│       └── forces_replacement
├── relationships[]    {source, target, status: added | removed | present}
├── hidden_unchanged   unchanged resources not adjacent to any change
└── drifted_resources  count of Terraform's resource_drift entries
```

## Decisions

**Identity is Terraform's address.** `terraform_data.api[0]` is the same
resource before and after, whether it is updated or replaced. The model never
contains two entries for one address.

**Replace is one resource.** Terraform's `["delete", "create"]` and
`["create", "delete"]` both become `action: "replace"`, with the order kept in
`replace_order`. The old and new objects are two states of one resource.

**Actions come only from `change.actions`.** Only Terraform's documented
sequences are mapped (`no-op`, `create`, `update`, `delete`, and the two
replace orders). Anything else — `forget`, deposed objects, an unknown
sequence — is rejected with a clear error instead of being approximated.
Data sources (`mode: "data"`) are reads, not infrastructure changes, and are
left out.

**Values are typed, never faked.**

- `unknown`: Terraform will only know the value after apply. Never replaced by
  `null`, `""` or a placeholder.
- `sensitive`: the value exists but is never copied into the model. Terraform
  includes sensitive values in plan JSON in clear text, and does not always
  propagate its sensitivity markers (for example into
  `terraform_data.output`), so any value equal to one Terraform marked
  sensitive elsewhere in the plan is redacted as well.
- `absent`: the attribute does not exist on that side (before a create, after
  a destroy). `absent` ↔ `null` is not reported as a change.

**Changed leaves instead of whole objects.** Resources carry the attributes
that change, not complete before/after documents. When a whole object becomes
unknown (e.g. `output` → known after apply), it is reported once at that path
rather than once per child.

**Relationships only claim what the plan proves.** See
[architecture.md](architecture.md#2-change-interpreter) for why `present`
exists and where each edge comes from. Edges point from the dependent to its
dependency (`api → database`).

## Failure modes

The API returns `422` with a readable reason for: JSON that is not a plan,
`format_version` other than `1.x`, plans Terraform marked `errored`, deposed
objects, and unsupported action sequences. Error messages name locations,
never values.
