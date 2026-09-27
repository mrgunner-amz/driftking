/**
 * Presentation helpers: how Change Model facts are worded and grouped.
 * Pure functions, no React, so they are easy to test.
 */

import type { Action, AttributeChange, ChangeSet, Resource, Value } from "./changeModel";

export type ChangeAction = Exclude<Action, "no-op">;

export const ACTION_META: Record<Action, { label: string; verb: string; glyph: string }> = {
  create: { label: "Created", verb: "create", glyph: "+" },
  update: { label: "Updated", verb: "update", glyph: "~" },
  replace: { label: "Replaced", verb: "replace", glyph: "±" },
  delete: { label: "Destroyed", verb: "destroy", glyph: "−" },
  "no-op": { label: "Unchanged", verb: "unchanged", glyph: "·" },
};

/** Summary order: most consequential first. */
export const SUMMARY_ORDER: ChangeAction[] = ["delete", "replace", "update", "create"];

/** "api[0]", 'web["blue"]', "database". */
export function displayName(resource: Resource): string {
  if (resource.index === null) return resource.name;
  const key = typeof resource.index === "number" ? resource.index : JSON.stringify(resource.index);
  return `${resource.name}[${key}]`;
}

/** "module.a.module.b" -> "a/b". */
export function moduleLabel(resource: Resource): string | null {
  if (!resource.module_address) return null;
  return resource.module_address.replace(/^module\./, "").replace(/\.module\./g, "/");
}

export function groupChanges(changeset: ChangeSet): { action: ChangeAction; resources: Resource[] }[] {
  return SUMMARY_ORDER.map((action) => ({
    action,
    resources: changeset.resources.filter((r) => r.action === action),
  })).filter((group) => group.resources.length > 0);
}

export function totalChanges(changeset: ChangeSet): number {
  const { create, update, replace, delete: destroy } = changeset.counts;
  return create + update + replace + destroy;
}

export function formatPath(path: AttributeChange["path"]): string {
  return path
    .map((segment, i) => (typeof segment === "number" ? `[${segment}]` : i === 0 ? segment : `.${segment}`))
    .join("");
}

export type FormattedValue = { text: string; tone: "value" | "unknown" | "sensitive" | "absent" };

/** Render one side of an attribute change. Never reveals sensitive data. */
export function formatValue(value: Value, maxLength = 48): FormattedValue {
  switch (value.kind) {
    case "unknown":
      return { text: "(known after apply)", tone: "unknown" };
    case "sensitive":
      return { text: "(sensitive value)", tone: "sensitive" };
    case "absent":
      return { text: "—", tone: "absent" };
    case "known": {
      const text = typeof value.value === "string" ? `"${value.value}"` : JSON.stringify(value.value);
      return {
        text: text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text,
        tone: "value",
      };
    }
  }
}

/** Why a resource is being replaced, in Terraform's own terms. */
export function replacementCause(resource: Resource): string | null {
  if (resource.action !== "replace") return null;
  const forcing = resource.changes.filter((c) => c.forces_replacement).map((c) => formatPath(c.path));
  if (forcing.length > 0) return `forced by ${forcing.join(", ")}`;
  if (resource.replace_paths.length > 0) {
    return `forced by ${resource.replace_paths.map((p) => formatPath(p)).join(", ")}`;
  }
  return null;
}

/** For in-place updates: which attributes change, e.g. "input.image, tags.env +2 more". */
export function updatedAttributes(resource: Resource, limit = 3): string | null {
  if (resource.action !== "update" || resource.changes.length === 0) return null;
  const paths = resource.changes.map((c) => formatPath(c.path));
  const shown = paths.slice(0, limit).join(", ");
  return paths.length > limit ? `${shown} +${paths.length - limit} more` : shown;
}

/** Attribute changes worth showing first: forcing changes, then known edits. */
export function sortedChanges(resource: Resource): AttributeChange[] {
  const rank = (c: AttributeChange) =>
    c.forces_replacement ? 0 : c.before.kind === "known" && c.after.kind === "known" ? 1 : 2;
  return [...resource.changes].sort((a, b) => rank(a) - rank(b));
}
