/** Builders for Change Model objects in tests. */

import type { Action, ChangeSet, Relationship, Resource } from "./changeModel";

export function resource(address: string, action: Action, overrides: Partial<Resource> = {}): Resource {
  const match = /^(?:(module\.[^.]+)\.)?([^.]+)\.([^.[]+)(?:\[(\d+)\])?$/.exec(address);
  return {
    address,
    module_address: match?.[1] ?? null,
    type: match?.[2] ?? "terraform_data",
    name: match?.[3] ?? address,
    index: match?.[4] !== undefined ? Number(match[4]) : null,
    provider_name: "terraform.io/builtin/terraform",
    action,
    action_reason: null,
    replace_order: action === "replace" ? "delete_before_create" : null,
    replace_paths: [],
    previous_address: null,
    importing: false,
    changes: [],
    ...overrides,
  };
}

export function changeset(resources: Resource[], relationships: Relationship[] = []): ChangeSet {
  const count = (action: Action) => resources.filter((r) => r.action === action).length;
  return {
    terraform_version: "1.16.4",
    format_version: "1.2",
    complete: true,
    counts: {
      create: count("create"),
      update: count("update"),
      replace: count("replace"),
      delete: count("delete"),
      no_op: count("no-op"),
    },
    resources,
    relationships,
    hidden_unchanged: 0,
    drifted_resources: 0,
  };
}
