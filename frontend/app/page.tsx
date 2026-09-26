type StatusRowProps = {
  label: string;
  value: string;
};

function StatusRow({ label, value }: StatusRowProps) {
  return (
    <div className="flex items-center justify-between gap-6 px-4 py-3 text-sm">
      <dt className="text-slate-300">{label}</dt>
      <dd className="flex items-center gap-2 text-slate-500">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-slate-600" />
        {value}
      </dd>
    </div>
  );
}

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-10 px-6 py-16">
      <header className="space-y-4">
        <span className="inline-block rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium tracking-wide text-amber-300">
          Early prototype
        </span>
        <h1 className="text-4xl font-semibold tracking-tight text-slate-50">DriftKing</h1>
        <p className="text-lg text-slate-400">See what changed in your infrastructure.</p>
      </header>

      <section aria-labelledby="status-heading" className="space-y-3">
        <h2
          id="status-heading"
          className="text-xs font-medium uppercase tracking-widest text-slate-500"
        >
          Status
        </h2>
        <dl className="divide-y divide-slate-800 rounded-lg border border-slate-800 bg-slate-900/50">
          <StatusRow label="Backend" value="Not connected yet" />
        </dl>
      </section>
    </main>
  );
}
