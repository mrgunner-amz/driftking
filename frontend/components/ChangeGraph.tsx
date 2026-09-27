import type { ChangeSet, Relationship, Resource } from "@/lib/changeModel";
import { NODE_HEIGHT, NODE_WIDTH, edgeKey, layoutGraph, routeEdges } from "@/lib/layout";
import { ACTION_META, displayName, moduleLabel } from "@/lib/present";

export type Phase = "before" | "after";

interface ChangeGraphProps {
  changeset: ChangeSet;
  phase: Phase;
  /** Skip transitions (used to reset to BEFORE before replaying). */
  instant?: boolean;
  focused?: string | null;
  selected?: string | null;
  onFocus?: (address: string | null) => void;
  onSelect?: (address: string) => void;
}

const MAX_LABEL = 22;
const truncate = (text: string, max = MAX_LABEL) =>
  text.length > max ? `${text.slice(0, max - 1)}…` : text;

/**
 * BEFORE and AFTER as one SVG. Every resource is rendered exactly once at a
 * fixed position; `data-phase` plus the per-action classes drive the CSS
 * transitions in globals.css. This component contains no timing logic.
 */
export function ChangeGraph({
  changeset,
  phase,
  instant = false,
  focused = null,
  selected = null,
  onFocus,
  onSelect,
}: ChangeGraphProps) {
  const { resources, relationships } = changeset;
  const layout = layoutGraph(
    resources.map((r) => r.address),
    relationships,
  );
  const paths = routeEdges(layout.positions, relationships);
  const related = relatedTo(focused ?? selected, relationships);

  return (
    <svg
      className={`dk-graph${instant ? " dk-instant" : ""}`}
      data-phase={phase}
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      width={layout.width}
      height={layout.height}
      role="img"
      aria-label={`Infrastructure graph, ${phase === "before" ? "before" : "after"} the change`}
    >
      <defs>
        {(["neutral", "create"] as const).map((tone) => (
          <marker
            key={tone}
            id={`dk-arrow-${tone}`}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 9 5 L 0 9 z" className={`dk-arrowhead dk-arrowhead--${tone}`} />
          </marker>
        ))}
      </defs>

      <g className="dk-edges">
        {relationships.map((rel) => {
          const d = paths[edgeKey(rel)];
          if (!d) return null;
          const dim = related !== null && !(related.has(rel.source) && related.has(rel.target));
          // Removed edges exist in BEFORE, so they carry the neutral arrowhead until they retract.
          const tone = rel.status === "added" ? "create" : "neutral";
          return (
            <g
              key={edgeKey(rel)}
              className={`dk-edge dk-edge--${rel.status}${dim ? " dk-dim" : ""}`}
              data-source={rel.source}
              data-target={rel.target}
            >
              <path d={d} pathLength={1} className="dk-edge__line" />
              {/* The arrowhead rides on its own path so it can appear after the line draws. */}
              <path d={d} className="dk-edge__head" markerEnd={`url(#dk-arrow-${tone})`} />
            </g>
          );
        })}
      </g>

      <g className="dk-nodes">
        {resources.map((resource) => {
          const position = layout.positions[resource.address];
          if (!position) return null;
          return (
            <GraphNode
              key={resource.address}
              resource={resource}
              x={position.x}
              y={position.y}
              dim={related !== null && !related.has(resource.address)}
              selected={selected === resource.address}
              onFocus={onFocus}
              onSelect={onSelect}
            />
          );
        })}
      </g>
    </svg>
  );
}

function relatedTo(address: string | null, relationships: Relationship[]): Set<string> | null {
  if (!address) return null;
  const related = new Set([address]);
  for (const rel of relationships) {
    if (rel.source === address) related.add(rel.target);
    if (rel.target === address) related.add(rel.source);
  }
  return related;
}

interface GraphNodeProps {
  resource: Resource;
  x: number;
  y: number;
  dim: boolean;
  selected: boolean;
  onFocus?: (address: string | null) => void;
  onSelect?: (address: string) => void;
}

function GraphNode({ resource, x, y, dim, selected, onFocus, onSelect }: GraphNodeProps) {
  const meta = ACTION_META[resource.action];
  const name = displayName(resource);
  const moduleName = moduleLabel(resource);
  const classes = [
    "dk-node",
    `dk-node--${resource.action}`,
    dim ? "dk-dim" : "",
    selected ? "dk-selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <g
      className={classes}
      transform={`translate(${x} ${y})`}
      data-address={resource.address}
      data-action={resource.action}
      role="button"
      tabIndex={0}
      aria-label={`${name}, ${resource.address}, ${meta.verb}`}
      aria-pressed={selected}
      onMouseEnter={() => onFocus?.(resource.address)}
      onMouseLeave={() => onFocus?.(null)}
      onFocus={() => onFocus?.(resource.address)}
      onBlur={() => onFocus?.(null)}
      onClick={() => onSelect?.(resource.address)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect?.(resource.address);
        }
      }}
    >
      <title>{`${resource.address} — ${meta.verb}`}</title>
      {moduleName && (
        <text className="dk-module" x={2} y={-7}>
          {truncate(`module.${moduleName}`, 28)}
        </text>
      )}
      {resource.action === "delete" && (
        // What was here, once the node itself has gone.
        <g className="dk-ghost">
          <rect width={NODE_WIDTH} height={NODE_HEIGHT} rx={10} />
          <text x={16} y={33}>
            {truncate(name)}
          </text>
        </g>
      )}
      <g className="dk-node__body">
        {(resource.action === "update" || resource.action === "replace") && (
          <rect className="dk-pulse" x={-3} y={-3} width={NODE_WIDTH + 6} height={NODE_HEIGHT + 6} rx={13} />
        )}
        {resource.action === "replace" ? (
          <>
            <Card className="dk-card dk-card--old" name={name} subtitle={resource.type} />
            <Card className="dk-card dk-card--new" name={name} subtitle={resource.type} />
          </>
        ) : (
          <Card className="dk-card" name={name} subtitle={resource.type} />
        )}
        {resource.action !== "no-op" && (
          <g className="dk-pill" transform={`translate(${NODE_WIDTH - 12} -9)`}>
            <rect x={-64} width={70} height={18} rx={9} />
            <text x={-29} y={12.5} textAnchor="middle">
              {`${meta.glyph} ${meta.verb}`}
            </text>
          </g>
        )}
      </g>
      <rect className="dk-selection" x={-4} y={-4} width={NODE_WIDTH + 8} height={NODE_HEIGHT + 8} rx={14} />
    </g>
  );
}

function Card({ className, name, subtitle }: { className: string; name: string; subtitle: string }) {
  return (
    <g className={className}>
      <rect className="dk-card__frame" width={NODE_WIDTH} height={NODE_HEIGHT} rx={10} />
      <rect className="dk-card__accent" x={0} y={12} width={3} height={NODE_HEIGHT - 24} rx={1.5} />
      <text className="dk-card__name" x={16} y={25}>
        {truncate(name)}
      </text>
      <text className="dk-card__type" x={16} y={43}>
        {truncate(subtitle, 26)}
      </text>
    </g>
  );
}
