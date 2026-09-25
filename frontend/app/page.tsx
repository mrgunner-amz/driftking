export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="text-5xl font-semibold tracking-tight">DriftKing</h1>

      <p className="max-w-md text-lg text-slate-400">
        See what changed in your infrastructure.
      </p>

      <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-4 py-2 text-sm text-slate-400">
        <span
          aria-hidden="true"
          className="h-2 w-2 rounded-full bg-slate-500"
        />
        Backend: not connected yet
      </div>
    </main>
  );
}
