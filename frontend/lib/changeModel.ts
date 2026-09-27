/**
 * DriftKing Change Model, as returned by the backend API.
 *
 * Mirrors backend/app/change_model.py. The frontend only ever sees this
 * model — never raw Terraform JSON — so Terraform's format stays a backend
 * concern.
 */

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type Action = "create" | "update" | "replace" | "delete" | "no-op";

export type Value =
  | { kind: "known"; value: JsonValue }
  | { kind: "unknown" }
  | { kind: "sensitive" }
  | { kind: "absent" };

export interface AttributeChange {
  path: (string | number)[];
  before: Value;
  after: Value;
  forces_replacement: boolean;
}

export interface Resource {
  address: string;
  module_address: string | null;
  type: string;
  name: string;
  index: number | string | null;
  provider_name: string;
  action: Action;
  action_reason: string | null;
  replace_order: "delete_before_create" | "create_before_destroy" | null;
  replace_paths: (string | number)[][];
  previous_address: string | null;
  importing: boolean;
  changes: AttributeChange[];
}

/**
 * - added: an endpoint is created, so the edge cannot exist before.
 * - removed: an endpoint is destroyed, so the edge cannot exist after.
 * - present: both endpoints exist on both sides; drawn in both states.
 */
export type RelationshipStatus = "added" | "removed" | "present";

export interface Relationship {
  source: string;
  target: string;
  status: RelationshipStatus;
}

export interface ActionCounts {
  create: number;
  update: number;
  replace: number;
  delete: number;
  no_op: number;
}

export interface ChangeSet {
  terraform_version: string | null;
  format_version: string;
  complete: boolean;
  counts: ActionCounts;
  resources: Resource[];
  relationships: Relationship[];
  hidden_unchanged: number;
  drifted_resources: number;
}
