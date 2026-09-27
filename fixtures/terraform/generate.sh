#!/usr/bin/env bash
# Regenerate the plan JSON fixtures in fixtures/plans/ from real Terraform runs.
#
# Everything happens in a temporary directory: .terraform/, lock files, state
# and binary plans never touch the repository. Only `terraform show -json`
# output is copied back, re-indented for readable diffs (content unchanged).
#
# Requirements: terraform >= 1.4 and python3 on PATH. No cloud credentials or
# provider downloads are needed; the configs only use the built-in
# terraform_data resource.
#
# Note: this script runs `terraform apply` against a throwaway local state to
# create the "before" side of the scenario. terraform_data manages no real
# infrastructure. DriftKing itself never runs Terraform.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$(cd "$here/../plans" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

export CHECKPOINT_DISABLE=1 TF_IN_AUTOMATION=1

tf() { terraform -chdir="$work/stack" "$@" -no-color >/dev/null; }

# Write `terraform show -json` output for the current tfplan to $1.
show_plan() {
  terraform -chdir="$work/stack" show -json tfplan | python3 -m json.tool --indent 2 > "$out/$1"
  echo "wrote fixtures/plans/$1"
}

echo "terraform: $(terraform version | head -n1)"

cp -R "$here/app-stack/modules" "$work/modules"
mkdir "$work/stack"

# 1. Empty state -> v1: everything is created.
cp "$here/app-stack/v1/main.tf" "$work/stack/main.tf"
tf init -input=false
tf plan -input=false -out=tfplan
show_plan app-stack-initial.json

# 2. Apply v1 to the throwaway state, then plan v1 again: nothing changes.
tf apply -input=false -auto-approve tfplan
tf plan -input=false -out=tfplan
show_plan app-stack-no-changes.json

# 3. v1 state -> v2: the mixed create/update/replace/delete scenario.
cp "$here/app-stack/v2/main.tf" "$work/stack/main.tf"
tf plan -input=false -out=tfplan
show_plan app-stack-upgrade.json
