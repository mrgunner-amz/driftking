import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { changeset, resource } from "@/lib/testing";
import { ChangeGraph } from "./ChangeGraph";

const cs = changeset(
  [
    resource("terraform_data.api[0]", "update"),
    resource("terraform_data.cache", "create"),
    resource("terraform_data.database", "replace"),
    resource("terraform_data.worker", "delete"),
    resource("terraform_data.network", "no-op"),
    resource("module.monitoring.terraform_data.health_check", "no-op"),
  ],
  [
    { source: "terraform_data.api[0]", target: "terraform_data.database", status: "present" },
    { source: "terraform_data.api[0]", target: "terraform_data.cache", status: "added" },
    { source: "terraform_data.worker", target: "terraform_data.database", status: "removed" },
    { source: "terraform_data.database", target: "terraform_data.network", status: "present" },
  ],
);

const render = (phase: "before" | "after", selected: string | null = null) =>
  renderToStaticMarkup(<ChangeGraph changeset={cs} phase={phase} selected={selected} />);

const count = (html: string, needle: string) => html.split(needle).length - 1;

describe("ChangeGraph", () => {
  it("renders every resource exactly once, whatever the phase", () => {
    for (const phase of ["before", "after"] as const) {
      const html = render(phase);
      for (const r of cs.resources) {
        expect(count(html, `data-address="${r.address}"`)).toBe(1);
      }
    }
  });

  it("only changes the phase attribute between BEFORE and AFTER", () => {
    // Identical markup means identical positions, labels and edges: the
    // transition transforms one graph rather than swapping two.
    const asBefore = render("after")
      .replace('data-phase="after"', 'data-phase="before"')
      .replace("after the change", "before the change");
    expect(asBefore).toBe(render("before"));
  });

  it("marks nodes and edges with their action and status", () => {
    const html = render("after");
    expect(html).toContain('class="dk-node dk-node--replace');
    expect(html).toContain('class="dk-node dk-node--delete');
    expect(html).toContain("dk-edge dk-edge--added");
    expect(html).toContain("dk-edge dk-edge--removed");
  });

  it("renders a replacement as one node with an old and a new state", () => {
    const html = render("after");
    // One replace resource in the model: one node, holding both states.
    expect(count(html, "dk-node--replace")).toBe(1);
    expect(count(html, "dk-card dk-card--old")).toBe(1);
    expect(count(html, "dk-card dk-card--new")).toBe(1);
  });

  it("labels module resources and what a destroyed node was", () => {
    const html = render("after");
    expect(html).toContain("module.monitoring");
    expect(html).toContain('class="dk-ghost"');
  });

  it("dims resources unrelated to the selection", () => {
    const html = render("after", "terraform_data.cache");
    const dimmed = [...html.matchAll(/class="dk-node [^"]*dk-dim[^"]*"[^>]*data-address="([^"]+)"/g)].map((m) => m[1]);
    expect(dimmed.sort()).toEqual([
      "module.monitoring.terraform_data.health_check",
      "terraform_data.database",
      "terraform_data.network",
      "terraform_data.worker",
    ]);
  });
});
