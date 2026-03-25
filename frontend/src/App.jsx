import React, { useState } from "react";
import APIKeyInput from "./components/APIKeyInput";
import PDFUpload from "./components/PDFUpload";
import ProgressDisplay from "./components/ProgressDisplay";
import ResultCard from "./components/ResultCard";

/**
 * App — top-level shell.
 * State machine: idle → processing → done | error
 */
export default function App() {
  const [apiKey, setApiKey] = useState("");
  const [appState, setAppState] = useState("idle"); // idle | processing | done | error
  const [jobId, setJobId] = useState(null);
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleSubmit = async (formData) => {
    try {
      setAppState("processing");
      const res = await fetch("/generate", { method: "POST", body: formData });
      if (!res.ok) throw new Error(await res.text());
      const { job_id } = await res.json();
      setJobId(job_id);
    } catch (e) {
      setErrorMsg(e.message);
      setAppState("error");
    }
  };

  const handleDone = (event) => {
    setResult({
      notebookB64: event.notebook_b64,
      colabUrl: event.colab_url,
      bullets: JSON.parse(event.message || "[]"),
    });
    setAppState("done");
  };

  const handleError = (msg) => {
    setErrorMsg(msg);
    setAppState("error");
  };

  const handleReset = () => {
    setAppState("idle");
    setJobId(null);
    setResult(null);
    setErrorMsg("");
  };

  return (
    <div data-testid="app-root" className="min-h-screen bg-surface flex flex-col">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="border-b border-border py-6">
        <div className="max-w-content mx-auto px-6">
          <span className="text-accent font-mono text-sm font-medium tracking-widest uppercase">
            Research Tool
          </span>
        </div>
      </header>

      {/* ── Main ────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-content mx-auto px-6 py-16 w-full">
        {/* Hero */}
        <div className="mb-12">
          <h1 className="text-5xl font-semibold text-text-primary leading-tight mb-4">
            Paper <span className="text-gradient">→</span> Notebook
          </h1>
          <p className="text-text-muted text-lg leading-relaxed max-w-lg">
            Upload a research paper. Get a production-quality Google Colab
            notebook — with working code, realistic experiments, and full
            theoretical annotations.
          </p>
        </div>

        <div className="space-y-6">
          {appState === "idle" && (
            <>
              <APIKeyInput value={apiKey} onChange={setApiKey} />
              <PDFUpload onSubmit={handleSubmit} apiKey={apiKey} disabled={false} />
            </>
          )}

          {appState === "processing" && (
            <ProgressDisplay
              jobId={jobId}
              onDone={handleDone}
              onError={handleError}
            />
          )}

          {appState === "done" && result && (
            <ResultCard
              title="Generated Notebook"
              bullets={result.bullets}
              notebookB64={result.notebookB64}
              colabUrl={result.colabUrl}
              onReset={handleReset}
            />
          )}

          {appState === "error" && (
            <div
              data-testid="error-state"
              className="border border-danger/30 rounded-lg p-6 bg-surface-1"
            >
              <p className="text-danger font-mono text-sm mb-4">{errorMsg}</p>
              <button
                onClick={handleReset}
                className="text-text-muted font-mono text-xs hover:text-text-primary"
              >
                Try Again →
              </button>
            </div>
          )}
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
