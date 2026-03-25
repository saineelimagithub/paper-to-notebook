import React from "react";

/**
 * App — top-level shell.
 * State machine: idle → processing → done | error
 * Components wired in Tasks 7–10.
 */
export default function App() {
  return (
    <div data-testid="app-root" className="min-h-screen bg-surface flex flex-col">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="border-b border-border py-6">
        <div className="max-w-content mx-auto px-6">
          <div className="flex items-center gap-3">
            <span className="text-accent font-mono text-sm font-medium tracking-widest uppercase">
              Research Tool
            </span>
          </div>
        </div>
      </header>

      {/* ── Main ────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-content mx-auto px-6 py-16 w-full">
        {/* Hero */}
        <div className="mb-16">
          <h1 className="text-5xl font-semibold text-text-primary leading-tight mb-4">
            Paper{" "}
            <span className="text-gradient">→</span>{" "}
            Notebook
          </h1>
          <p className="text-text-muted text-lg leading-relaxed max-w-lg">
            Upload a research paper. Get a production-quality Google Colab
            notebook — with working code, realistic experiments, and full
            theoretical annotations.
          </p>
        </div>

        {/* Placeholder — components injected in Tasks 7–10 */}
        <div className="space-y-4">
          <div className="border border-border rounded-lg p-6 bg-surface-1">
            <p className="text-text-muted font-mono text-sm">
              // APIKeyInput — Task 7
            </p>
          </div>
          <div className="border border-border rounded-lg p-6 bg-surface-1">
            <p className="text-text-muted font-mono text-sm">
              // PDFUpload — Task 8
            </p>
          </div>
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer className="border-t border-border py-6">
        <div className="max-w-content mx-auto px-6">
          <p className="text-text-muted font-mono text-xs">
            Your API key is never stored. All processing happens in your session only.
          </p>
        </div>
      </footer>
    </div>
  );
}
