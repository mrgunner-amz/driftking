import type { ChangeSet, Resource } from "@/lib/changeModel";
import {
  ACTION_META,
  type ChangeAction,
  displayName,
  formatPath,
  formatValue,
  groupChanges,
  moduleLabel,
  replacementCause,
  sortedChanges,
  totalChanges,
  updatedAttributes,
} from "@/lib/present";

interface ChangeSummaryProps {
  changeset: ChangeSet;
  selected: string | null;
  onSelect: (address: string) => void;
  onFocus: (address: string | null) => void;
}

const ACTION_TEXT: Record<ChangeAction, string> = {
  create: "text-create",
  update: "text-update",
  replace: "text-replace",
  delete: "text-delete",
};

export function ChangeSummary({ changeset, selected, onSelect, onFocus }: ChangeSummaryProps) {
  const total = totalChanges(changeset);
  const groups = groupChanges(changeset);
  const context = changeset.resources.filter((r) => r.action === "no-op");

  return (
    <div className="flex flex-col gap-6">
      <header className="space-y-3">
        <h2 className="text-sm font-medium text-fg">What changed?</h2>
        <p className="text-2xl font-semibold tracking-tight text-fg">
          {total === 0 ? "No changes" : `${total} ${total === 1 ? "change" : "changes"}`}
        </p>
        {total > 0 && (
          <ul className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs" aria-label="Changes by action">
            {groups.map(({ action, resources }) => (
              <li key={action} className={ACTION_TEXT[action]}>
                {ACTION_META[action].glyph} {resources.length} {ACTION_META[action].verb}
              </li>
            ))}
          </ul>
        )}
      </header>

      {groups.map(({ action, resources }) => (
        <section key={action} aria-labelledby={`group-${action}`}>
          <h3
            id={`group-${action}`}
            className={`mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] ${ACTION_TEXT[action]}`}
          >
            {ACTION_META[action].label}
          </h3>
          <ul className="space-y-1">
            {resources.map((resource) => (
              <li key={resource.address}>
                <SummaryItem
                  resource={resource}
                  action={action}
                  expanded={selected === resource.address}
                  onSelect={onSelect}
                  onFocus={onFocus}
                />
              </li>
            ))}
          </ul>
        </section>
      ))}

      {(context.length > 0 || changeset.hidden_unchanged > 0) && (
        <section className="space-y-1.5 border-t border-line pt-4 text-xs text-muted">
          {context.length > 0 && (
            <p>
              <span className="text-faint">Unchanged, shown for context: </span>
              {context.map((r, i) => (
                <span key={r.address}>
                  {i > 0 && ", "}
                  <span className="font-mono text-fg/80">{displayName(r)}</span>
                </span>
              ))}
            </p>
          )}
          {changeset.hidden_unchanged > 0 && (
            <p className="text-faint">
              {changeset.hidden_unchanged} unchanged {changeset.hidden_unchanged === 1 ? "resource" : "resources"}{" "}
              not connected to a change {changeset.hidden_unchanged === 1 ? "is" : "are"} not shown.
            </p>
          )}
        </section>
      )}
    </div>
  );
}

interface SummaryItemProps {
  resource: Resource;
  action: ChangeAction;
  expanded: boolean;
  onSelect: (address: string) => void;
  onFocus: (address: string | null) => void;
}

function SummaryItem({ resource, action, expanded, onSelect, onFocus }: SummaryItemProps) {
  const moduleName = moduleLabel(resource);
  const cause = replacementCause(resource);
  const updated = updatedAttributes(resource);
  const detailsId = `changes-${resource.address}`;

  return (
    <div
      className={`rounded-md border transition-colors ${
        expanded ? "border-line bg-raised" : "border-transparent hover:bg-raised/60"
      }`}
      onMouseEnter={() => onFocus(resource.address)}
      onMouseLeave={() => onFocus(null)}
    >
      <button
        type="button"
        className="flex w-full items-start gap-3 px-3 py-2 text-left"
        aria-expanded={expanded}
        aria-controls={detailsId}
        onClick={() => onSelect(resource.address)}
        onFocus={() => onFocus(resource.address)}
        onBlur={() => onFocus(null)}
      >
        <span aria-hidden className={`mt-px w-3 font-mono text-sm ${ACTION_TEXT[action]}`}>
          {ACTION_META[action].glyph}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="truncate font-mono text-sm text-fg">{displayName(resource)}</span>
            {moduleName && (
              <span className="shrink-0 rounded border border-line px-1 font-mono text-[10px] text-muted">
                {moduleName}
              </span>
            )}
          </span>
          <span className="block truncate font-mono text-[11px] text-faint">{resource.address}</span>
          {cause && <span className="mt-0.5 block text-[11px] text-replace">{cause}</span>}
          {updated && <span className="mt-0.5 block truncate font-mono text-[11px] text-update/90">{updated}</span>}
        </span>
        <svg
          aria-hidden
          viewBox="0 0 10 10"
          className={`mt-1.5 h-2.5 w-2.5 shrink-0 fill-none stroke-faint transition-transform ${expanded ? "rotate-90" : ""}`}
        >
          <path d="M3.5 1.5 L7 5 L3.5 8.5" strokeWidth="1.5" />
        </svg>
      </button>

      {expanded && (
        <div id={detailsId} className="px-3 pb-3 pl-9">
          {resource.changes.length === 0 ? (
            <p className="text-xs text-faint">No attribute-level changes reported.</p>
          ) : (
            <dl className="space-y-1.5">
              {sortedChanges(resource).map((change) => {
                const before = formatValue(change.before, 36);
                const after = formatValue(change.after, 36);
                return (
                  <div key={formatPath(change.path)} className="font-mono text-[11px] leading-snug">
                    <dt className="flex flex-wrap items-center gap-x-1.5 text-muted">
                      {formatPath(change.path)}
                      {change.forces_replacement && (
                        <span className="rounded bg-replace/15 px-1 text-[10px] whitespace-nowrap text-replace">forces replacement</span>
                      )}
                    </dt>
                    <dd className="flex flex-wrap items-baseline gap-x-1.5 [overflow-wrap:anywhere]">
                      <ValueText {...before} />
                      <span aria-hidden className="text-faint">→</span>
                      <span className="sr-only">becomes</span>
                      <ValueText {...after} />
                    </dd>
                  </div>
                );
              })}
            </dl>
          )}
        </div>
      )}
    </div>
  );
}

function ValueText({ text, tone }: { text: string; tone: "value" | "unknown" | "sensitive" | "absent" }) {
  const style = {
    value: "text-fg",
    unknown: "italic text-update/90",
    sensitive: "italic text-muted",
    absent: "text-faint",
  }[tone];
  return <span className={style}>{text}</span>;
}
