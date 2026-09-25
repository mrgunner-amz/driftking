# Fixtures

Sample Terraform plan JSON used for development and tests.

This directory is currently empty apart from this file — the parser that would
consume these fixtures does not exist yet.

## Generating a fixture

```bash
terraform plan -out=plan.tfplan
terraform show -json plan.tfplan > fixtures/<name>.json
```

## Guidelines

- **Scrub before committing.** Plan JSON can contain account IDs, ARNs,
  bucket names, IP ranges, tags and — for some providers — secret values in
  `after_sensitive` / attribute bodies. Review every fixture by hand and
  replace anything real with placeholder values. Never commit a fixture
  straight out of a production workspace.
- **Keep them small.** One scenario per file, named for what it exercises:
  `create-only.json`, `in-place-update.json`, `forces-replacement.json`,
  `unknown-after-apply.json`, `module-nested.json`.
- **Record the Terraform version.** The JSON plan representation is versioned
  via `format_version`; note which Terraform version produced each fixture.
