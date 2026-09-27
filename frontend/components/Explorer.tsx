"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, fixtureChanges, interpretPlan, listFixtures } from "@/lib/api";
import type { ChangeSet } from "@/lib/changeModel";
import { ChangeGraph, type Phase } from "./ChangeGraph";
import { ChangeSummary } from "./ChangeSummary";

const DEFAULT_FIXTURE = "app-stack-upgrade";
/** Pause on BEFORE after loading so the starting point registers. */
const AUTOPLAY_DELAY_MS = 900;

type Source = { kind: "fixture"; name: string } | { kind: "upload"; name: string };

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; changeset: ChangeSet };

const nextFrame = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

export function Explorer() {
  const [fixtures, setFixtures] = useState<string[]>([]);
  const [source, setSource] = useState<Source | null>(null);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [phase, setPhase] = useState<Phase>("before");
  const [instant, setInstant] = useState(true);
  const [focused, setFocused] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const playToken = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);

  /** Snap to BEFORE, then animate to AFTER. */
  const play = useCallback(async () => {
    const token = ++playToken.current;
    setInstant(true);
    setPhase("before");
    await nextFrame();
    await nextFrame();
    if (token !== playToken.current) return;
    setInstant(false);
    await nextFrame();
    if (token !== playToken.current) return;
    setPhase("after");
  }, []);

  /** Animate to the requested phase from wherever we are. */
  const showPhase = useCallback((next: Phase) => {
    playToken.current++;
    setInstant(false);
    setPhase(next);
  }, []);

  const present = useCallback(
    (changeset: ChangeSet) => {
      setSelected(null);
      setFocused(null);
      setInstant(true);
      setPhase("before");
      setState({ status: "ready", changeset });
      const token = ++playToken.current;
      window.setTimeout(() => {
        if (token === playToken.current) void play();
      }, AUTOPLAY_DELAY_MS);
    },
    [play],
  );

  const loadFixture = useCallback(
    async (name: string) => {
      setSource({ kind: "fixture", name });
      setState({ status: "loading" });
      try {
        present(await fixtureChanges(name));
      } catch (error) {
        setState({ status: "error", message: errorMessage(error) });
      }
    },
    [present],
  );

  useEffect(() => {
    let cancelled = false;
    listFixtures()
      .then(({ fixtures: found }) => {
        if (cancelled) return;
        const names = found.map((f) => f.name);
        setFixtures(names);
        const initial = names.includes(DEFAULT_FIXTURE) ? DEFAULT_FIXTURE : names[0];
        if (initial) void loadFixture(initial);
        else setState({ status: "error", message: "No bundled plan fixtures were found." });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: "error", message: errorMessage(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [loadFixture]);

  const onUpload = async (file: File) => {
    setSource({ kind: "upload", name: file.name });
    setState({ status: "loading" });
    try {
      present(await interpretPlan(await file.text()));
    } catch (error) {
      setState({ status: "error", message: errorMessage(error) });
    }
  };

  const toggleSelected = (address: string) =>
    setSelected((current) => (current === address ? null : address));

  const changeset = state.status === "ready" ? state.changeset : null;
  const hasChanges = changeset !== null && changeset.resources.length > 0;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-line px-5 py-3">
        <div className="flex items-baseline gap-3">
          <span className="text-[15px] font-semibold tracking-tight text-fg">DriftKing</span>
          <span className="text-xs text-faint">Terraform change explorer</span>
          <span className="rounded-full border border-update/30 px-2 py-px text-[10px] font-medium text-update">
            early prototype
          </span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <label className="sr-only" htmlFor="plan-source">
            Plan
          </label>
          <select
            id="plan-source"
            className="h-8 rounded-md border border-line bg-panel px-2 font-mono text-xs text-fg outline-none focus-visible:ring-2 focus-visible:ring-focus"
            value={source?.kind === "fixture" ? source.name : ""}
            onChange={(event) => void loadFixture(event.target.value)}
          >
            {source?.kind === "upload" && <option value="">{source.name}</option>}
            {fixtures.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="h-8 rounded-md border border-line bg-panel px-3 text-xs text-fg hover:bg-raised focus-visible:ring-2 focus-visible:ring-focus focus-visible:outline-none"
            onClick={() => fileInput.current?.click()}
          >
            Open plan JSON…
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) void onUpload(file);
            }}
          />
        </div>
      </header>

      <main className="grid flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_400px]">
        <section className="flex min-h-[480px] flex-col border-b border-line lg:border-r lg:border-b-0" aria-label="Infrastructure graph">
          <div className="flex flex-wrap items-center gap-3 px-5 pt-4">
            <PhaseControl phase={phase} disabled={!hasChanges} onChange={showPhase} onPlay={() => void play()} />
            {changeset && (
              <p className="ml-auto font-mono text-[11px] text-faint">
                {source?.name} · terraform {changeset.terraform_version ?? "?"} · plan format {changeset.format_version}
              </p>
            )}
          </div>

          <div className="dk-canvas relative m-5 flex flex-1 items-center justify-center overflow-auto rounded-xl border border-line">
            {state.status === "loading" && <p className="text-sm text-faint">Interpreting plan…</p>}
            {state.status === "error" && (
              <div role="alert" className="max-w-md px-6 text-center">
                <p className="text-sm font-medium text-delete">Could not show this plan</p>
                <p className="mt-2 text-sm text-muted">{state.message}</p>
              </div>
            )}
            {changeset && !hasChanges && (
              <div className="px-6 text-center">
                <p className="text-sm font-medium text-fg">No changes</p>
                <p className="mt-2 text-sm text-muted">
                  Terraform plans no changes to the {changeset.counts.no_op} managed{" "}
                  {changeset.counts.no_op === 1 ? "resource" : "resources"} in this plan.
                </p>
              </div>
            )}
            {changeset && hasChanges && (
              <>
                <span
                  aria-live="polite"
                  className="pointer-events-none absolute top-4 left-5 font-mono text-[11px] font-semibold tracking-[0.2em] text-faint uppercase"
                >
                  {phase}
                </span>
                {phase === "before" && changeset.resources.every((r) => r.action === "create") && (
                  <p className="pointer-events-none absolute inset-x-0 top-1/2 text-center text-sm text-faint">
                    Nothing exists yet: every resource shown is created by this plan.
                  </p>
                )}
                <div className="p-6">
                  <ChangeGraph
                    changeset={changeset}
                    phase={phase}
                    instant={instant}
                    focused={focused}
                    selected={selected}
                    onFocus={setFocused}
                    onSelect={toggleSelected}
                  />
                </div>
              </>
            )}
          </div>

          {hasChanges && <Legend />}
        </section>

        <aside className="px-5 py-5 lg:max-h-[calc(100vh-57px)] lg:overflow-y-auto" aria-label="Change summary">
          {changeset ? (
            <>
              <ChangeSummary changeset={changeset} selected={selected} onSelect={toggleSelected} onFocus={setFocused} />
              <PlanNotes changeset={changeset} />
            </>
          ) : (
            <p className="text-sm text-faint">{state.status === "loading" ? "Loading…" : ""}</p>
          )}
        </aside>
      </main>
    </div>
  );
}

function PhaseControl({
  phase,
  disabled,
  onChange,
  onPlay,
}: {
  phase: Phase;
  disabled: boolean;
  onChange: (phase: Phase) => void;
  onPlay: () => void;
}) {
  const option = (value: Phase, label: string) => (
    <button
      type="button"
      role="radio"
      aria-checked={phase === value}
      disabled={disabled}
      onClick={() => onChange(value)}
      className={`h-7 rounded px-3 text-xs font-medium transition-colors focus-visible:ring-2 focus-visible:ring-focus focus-visible:outline-none disabled:opacity-40 ${
        phase === value ? "bg-raised text-fg shadow-sm" : "text-muted hover:text-fg"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="flex items-center gap-2">
      <div role="radiogroup" aria-label="Show infrastructure" className="flex gap-0.5 rounded-md border border-line bg-panel p-0.5">
        {option("before", "Before")}
        {option("after", "After")}
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={onPlay}
        className="flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs text-muted hover:bg-raised hover:text-fg focus-visible:ring-2 focus-visible:ring-focus focus-visible:outline-none disabled:opacity-40"
      >
        <svg aria-hidden width="10" height="10" viewBox="0 0 10 10" className="fill-current">
          <path d="M1 0.5 L9 5 L1 9.5 z" />
        </svg>
        Play transition
      </button>
    </div>
  );
}

function Legend() {
  const item = (swatch: string, label: string) => (
    <li className="flex items-center gap-1.5">
      <span aria-hidden className={`h-2 w-2 rounded-full ${swatch}`} />
      {label}
    </li>
  );
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 pb-4 text-[11px] text-muted" aria-label="Legend">
      {item("bg-create", "created")}
      {item("bg-update", "updated")}
      {item("bg-replace", "replaced")}
      {item("bg-delete", "destroyed")}
      {item("bg-node-stroke", "unchanged context")}
      <li className="flex items-center gap-1.5">
        <svg aria-hidden width="22" height="8" viewBox="0 0 22 8" className="stroke-edge">
          <path d="M1 4 H18" strokeWidth="1.5" />
          <path d="M16 1 L20 4 L16 7" fill="none" strokeWidth="1.5" />
        </svg>
        depends on
      </li>
    </ul>
  );
}

function PlanNotes({ changeset }: { changeset: ChangeSet }) {
  const notes: string[] = [];
  if (!changeset.complete) {
    notes.push("Terraform marked this plan as incomplete; applying it would not converge on the configuration.");
  }
  if (changeset.drifted_resources > 0) {
    notes.push(
      `Terraform detected ${changeset.drifted_resources} ${
        changeset.drifted_resources === 1 ? "resource" : "resources"
      } changed outside Terraform. Drift is not visualized yet.`,
    );
  }
  if (changeset.relationships.some((r) => r.status === "present")) {
    notes.push(
      "Dependencies come from the planned configuration. Terraform does not record the previous configuration, so edges between resources that exist on both sides are drawn in both states.",
    );
  }
  if (notes.length === 0) return null;
  return (
    <ul className="mt-6 space-y-2 border-t border-line pt-4 text-[11px] leading-relaxed text-faint">
      {notes.map((note) => (
        <li key={note}>{note}</li>
      ))}
    </ul>
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong while loading the plan.";
}
