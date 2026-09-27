import { describe, expect, it } from "vitest";

import {
  displayName,
  formatPath,
  formatValue,
  groupChanges,
  moduleLabel,
  replacementCause,
  totalChanges,
  updatedAttributes,
} from "./present";
import { changeset, resource } from "./testing";

describe("naming", () => {
  it("includes the index for counted and for_each resources", () => {
    expect(displayName(resource("terraform_data.api[2]", "create"))).toBe("api[2]");
    expect(displayName(resource("aws_s3_bucket.logs", "create", { index: "blue" }))).toBe('logs["blue"]');
    expect(displayName(resource("terraform_data.db", "update"))).toBe("db");
  });

  it("shortens module addresses", () => {
    expect(moduleLabel(resource("module.monitoring.terraform_data.hc", "no-op"))).toBe("monitoring");
    expect(moduleLabel(resource("x.y", "no-op", { module_address: "module.a.module.b" }))).toBe("a/b");
    expect(moduleLabel(resource("terraform_data.db", "no-op"))).toBeNull();
  });

  it("formats attribute paths", () => {
    expect(formatPath(["input", "targets", 2])).toBe("input.targets[2]");
  });
});

describe("formatValue", () => {
  it("never reveals sensitive values and keeps unknowns unknown", () => {
    expect(formatValue({ kind: "sensitive" })).toEqual({ text: "(sensitive value)", tone: "sensitive" });
    expect(formatValue({ kind: "unknown" })).toEqual({ text: "(known after apply)", tone: "unknown" });
    expect(formatValue({ kind: "absent" }).tone).toBe("absent");
  });

  it("quotes strings, serializes other JSON and truncates long values", () => {
    expect(formatValue({ kind: "known", value: "16" }).text).toBe('"16"');
    expect(formatValue({ kind: "known", value: 3 }).text).toBe("3");
    expect(formatValue({ kind: "known", value: null }).text).toBe("null");
    expect(formatValue({ kind: "known", value: "x".repeat(100) }, 10).text).toHaveLength(10);
  });
});

describe("summary grouping", () => {
  const cs = changeset([
    resource("terraform_data.cache", "create"),
    resource("terraform_data.api[0]", "update"),
    resource("terraform_data.network", "no-op"),
    resource("terraform_data.database", "replace"),
    resource("terraform_data.worker", "delete"),
  ]);

  it("orders groups by consequence and leaves out unchanged context", () => {
    expect(groupChanges(cs).map((g) => g.action)).toEqual(["delete", "replace", "update", "create"]);
    expect(totalChanges(cs)).toBe(4);
  });

  it("omits empty groups", () => {
    const onlyCreate = changeset([resource("terraform_data.a", "create")]);
    expect(groupChanges(onlyCreate).map((g) => g.action)).toEqual(["create"]);
  });
});

describe("change explanations", () => {
  it("names the attribute forcing a replacement", () => {
    const db = resource("terraform_data.database", "replace", {
      replace_paths: [["triggers_replace"]],
      changes: [
        {
          path: ["triggers_replace", "engine_version"],
          before: { kind: "known", value: "15" },
          after: { kind: "known", value: "16" },
          forces_replacement: true,
        },
      ],
    });
    expect(replacementCause(db)).toBe("forced by triggers_replace.engine_version");
    expect(replacementCause(resource("terraform_data.x", "update"))).toBeNull();
  });

  it("lists updated attributes, capped", () => {
    const change = (name: string) => ({
      path: [name],
      before: { kind: "absent" } as const,
      after: { kind: "unknown" } as const,
      forces_replacement: false,
    });
    const api = resource("terraform_data.api[0]", "update", {
      changes: ["a", "b", "c", "d", "e"].map(change),
    });
    expect(updatedAttributes(api)).toBe("a, b, c +2 more");
    expect(updatedAttributes(resource("terraform_data.x", "create"))).toBeNull();
  });
});
