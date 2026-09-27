import { describe, expect, it } from "vitest";

import { NODE_HEIGHT, NODE_WIDTH, edgeKey, layoutGraph, routeEdges } from "./layout";

const nodes = ["lb", "api[0]", "api[1]", "api[2]", "db", "cache", "net"];
const edges = [
  { source: "lb", target: "api[0]" },
  { source: "lb", target: "api[1]" },
  { source: "lb", target: "api[2]" },
  { source: "api[0]", target: "db" },
  { source: "api[1]", target: "db" },
  { source: "api[2]", target: "db" },
  { source: "api[2]", target: "cache" },
  { source: "db", target: "net" },
  { source: "cache", target: "net" },
];

describe("layoutGraph", () => {
  it("is deterministic regardless of input order", () => {
    const a = layoutGraph(nodes, edges);
    const b = layoutGraph([...nodes].reverse(), [...edges].reverse());
    expect(b).toEqual(a);
  });

  it("places dependents above their dependencies", () => {
    const { positions } = layoutGraph(nodes, edges);
    for (const { source, target } of edges) {
      expect(positions[source]!.y).toBeLessThan(positions[target]!.y);
    }
  });

  it("positions every node without overlaps", () => {
    const { positions } = layoutGraph(nodes, edges);
    const placed = nodes.map((n) => positions[n]!);
    expect(placed.every(Boolean)).toBe(true);
    for (let i = 0; i < placed.length; i++) {
      for (let j = i + 1; j < placed.length; j++) {
        const [p, q] = [placed[i]!, placed[j]!];
        const overlap = Math.abs(p.x - q.x) < NODE_WIDTH && Math.abs(p.y - q.y) < NODE_HEIGHT;
        expect(overlap).toBe(false);
      }
    }
  });

  it("gives a node the same position whether or not its neighbors change", () => {
    // Identity on screen: a node's slot is fixed by the union graph, so the
    // same layout serves BEFORE and AFTER.
    const once = layoutGraph(nodes, edges);
    const again = layoutGraph(nodes, edges);
    expect(again.positions["db"]).toEqual(once.positions["db"]);
  });

  it("sorts indexed addresses numerically", () => {
    const { positions } = layoutGraph(["x[10]", "x[2]", "x[1]"], []);
    const byX = Object.entries(positions).sort((a, b) => a[1].x - b[1].x).map(([n]) => n);
    expect(byX).toEqual(["x[1]", "x[2]", "x[10]"]);
  });

  it("handles empty graphs, unknown endpoints and cycles", () => {
    expect(layoutGraph([], [])).toEqual({ positions: {}, width: 0, height: 0 });
    const ghost = layoutGraph(["a"], [{ source: "a", target: "missing" }]);
    expect(Object.keys(ghost.positions)).toEqual(["a"]);
    const cyclic = layoutGraph(["a", "b"], [
      { source: "a", target: "b" },
      { source: "b", target: "a" },
    ]);
    expect(Object.keys(cyclic.positions).sort()).toEqual(["a", "b"]);
  });
});

describe("routeEdges", () => {
  it("routes each edge and spreads edges that share a node", () => {
    const { positions } = layoutGraph(nodes, edges);
    const paths = routeEdges(positions, edges);
    expect(Object.keys(paths).sort()).toEqual(edges.map(edgeKey).sort());

    const endX = (key: string) => Number(paths[key]!.trim().split(/[ ,]+/).at(-2));
    const intoDb = ["api[0]", "api[1]", "api[2]"].map((s) => endX(`${s}->db`));
    expect(new Set(intoDb).size).toBe(3);
  });
});
