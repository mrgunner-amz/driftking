/**
 * Deterministic layered layout for the change neighborhood.
 *
 * The layout is computed once over the *union* of BEFORE and AFTER, so every
 * resource keeps a single position in both states. That is what lets the
 * transition transform one graph into the other instead of swapping
 * diagrams: identity on screen follows identity in the Change Model.
 *
 * Dependents sit above what they depend on (api above database), matching
 * the direction of the arrows.
 */

export const NODE_WIDTH = 184;
export const NODE_HEIGHT = 58;
const COLUMN_GAP = 28;
const ROW_GAP = 76;
const PADDING = 36;
const ORDERING_SWEEPS = 4;

export interface Point {
  x: number;
  y: number;
}

export interface GraphLayout {
  /** Top-left corner of each node, keyed by resource address. */
  positions: Record<string, Point>;
  width: number;
  height: number;
}

export interface LayoutEdge {
  source: string;
  target: string;
}

const collator = new Intl.Collator("en", { numeric: true });
export const compareAddress = (a: string, b: string) => collator.compare(a, b);

export function layoutGraph(addresses: readonly string[], edges: readonly LayoutEdge[]): GraphLayout {
  const nodes = [...new Set(addresses)].sort(compareAddress);
  if (nodes.length === 0) return { positions: {}, width: 0, height: 0 };
  const known = new Set(nodes);
  const deps = new Map<string, string[]>(nodes.map((n) => [n, []]));
  const neighbors = new Map<string, string[]>(nodes.map((n) => [n, []]));
  for (const { source, target } of edges) {
    if (!known.has(source) || !known.has(target) || source === target) continue;
    deps.get(source)!.push(target);
    neighbors.get(source)!.push(target);
    neighbors.get(target)!.push(source);
  }

  // Longest path to a node with no dependencies: 0 = bottom row.
  const depth = new Map<string, number>();
  const visiting = new Set<string>();
  const depthOf = (node: string): number => {
    const cached = depth.get(node);
    if (cached !== undefined) return cached;
    if (visiting.has(node)) return 0; // Cycles are not expected from Terraform; don't loop.
    visiting.add(node);
    const value = Math.max(-1, ...deps.get(node)!.map(depthOf)) + 1;
    visiting.delete(node);
    depth.set(node, value);
    return value;
  };
  nodes.forEach(depthOf);

  const maxDepth = Math.max(...depth.values());
  const layers: string[][] = Array.from({ length: maxDepth + 1 }, () => []);
  for (const node of nodes) layers[maxDepth - depth.get(node)!]!.push(node);

  // Barycenter ordering reduces crossings; ties keep the previous order.
  const order = new Map<string, number>();
  const relative = (node: string) => {
    const layer = layers[maxDepth - depth.get(node)!]!;
    return (order.get(node)! + 0.5) / layer.length;
  };
  const renumber = () => layers.forEach((layer) => layer.forEach((n, i) => order.set(n, i)));
  renumber();
  for (let sweep = 0; sweep < ORDERING_SWEEPS; sweep++) {
    const sequence = sweep % 2 === 0 ? layers : [...layers].reverse();
    for (const layer of sequence) {
      const score = new Map(
        layer.map((node) => {
          const adjacent = neighbors.get(node)!;
          const value = adjacent.length
            ? adjacent.reduce((sum, n) => sum + relative(n), 0) / adjacent.length
            : relative(node);
          return [node, value] as const;
        }),
      );
      layer.sort((a, b) => score.get(a)! - score.get(b)! || order.get(a)! - order.get(b)!);
      renumber();
    }
  }

  const widest = Math.max(...layers.map((layer) => layer.length));
  const contentWidth = widest * NODE_WIDTH + (widest - 1) * COLUMN_GAP;
  const positions: Record<string, Point> = {};
  layers.forEach((layer, row) => {
    const rowWidth = layer.length * NODE_WIDTH + (layer.length - 1) * COLUMN_GAP;
    const offset = PADDING + (contentWidth - rowWidth) / 2;
    layer.forEach((node, column) => {
      positions[node] = {
        x: offset + column * (NODE_WIDTH + COLUMN_GAP),
        y: PADDING + row * (NODE_HEIGHT + ROW_GAP),
      };
    });
  });

  return {
    positions,
    width: contentWidth + PADDING * 2,
    height: layers.length * NODE_HEIGHT + (layers.length - 1) * ROW_GAP + PADDING * 2,
  };
}

export const edgeKey = (edge: LayoutEdge) => `${edge.source}->${edge.target}`;

const PORT_SPREAD = NODE_WIDTH * 0.62;
const MAX_PORT_GAP = 26;

/**
 * SVG paths for each edge, keyed by `edgeKey`, from the bottom of the
 * dependent to the top of its dependency.
 *
 * Edges attach at distinct ports spread along a node's edge, ordered by
 * where the other end sits, so several arrows into one node stay separable
 * instead of converging on a single point.
 */
export function routeEdges(positions: Record<string, Point>, edges: readonly LayoutEdge[]): Record<string, string> {
  const center = (address: string) => positions[address]!.x + NODE_WIDTH / 2;
  const drawable = edges.filter((e) => positions[e.source] && positions[e.target]);

  const portX = (node: string, ends: string[], other: string): number => {
    const sorted = [...ends].sort((a, b) => center(a) - center(b) || compareAddress(a, b));
    const gap = Math.min(MAX_PORT_GAP, PORT_SPREAD / Math.max(sorted.length, 1));
    return center(node) + (sorted.indexOf(other) - (sorted.length - 1) / 2) * gap;
  };
  const outgoing = new Map<string, string[]>();
  const incoming = new Map<string, string[]>();
  for (const { source, target } of drawable) {
    outgoing.set(source, [...(outgoing.get(source) ?? []), target]);
    incoming.set(target, [...(incoming.get(target) ?? []), source]);
  }

  const paths: Record<string, string> = {};
  for (const edge of drawable) {
    const from = positions[edge.source]!;
    const to = positions[edge.target]!;
    const x1 = portX(edge.source, outgoing.get(edge.source)!, edge.target);
    const x2 = portX(edge.target, incoming.get(edge.target)!, edge.source);
    const y1 = from.y + NODE_HEIGHT;
    const y2 = to.y - 6; // leave room for the arrowhead
    const bend = Math.max(28, (y2 - y1) / 2);
    paths[edgeKey(edge)] = `M ${x1} ${y1} C ${x1} ${y1 + bend}, ${x2} ${y2 - bend}, ${x2} ${y2}`;
  }
  return paths;
}
