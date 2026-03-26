import React, { useState } from "react";

export default function ResultCard({ title, bullets, notebookB64, colabUrl, findings, onReset }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const hasFindings = findings && findings.length > 0;

  const handleDownload = () => {
    const bytes = atob(notebookB64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    const blob = new Blob([arr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const safeName = title.replace(/[^a-z0-9]/gi, "_").toLowerCase();
    a.href = url;
    a.download = `${safeName}_notebook.ipynb`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      data-testid="result-card"
      className="space-y-6 border border-accent/30 rounded-lg p-6 bg-surface-1 glow-accent"
    >
      <div>
        <p className="text-accent font-mono text-xs uppercase tracking-widest mb-2">
          Notebook Ready
        </p>
        <h2 className="text-text-primary text-xl font-semibold leading-tight">
          {title}
        </h2>
      </div>

      {bullets?.length > 0 && (
        <ul className="space-y-2">
          {bullets.map((b, i) => (
            <li key={i} className="flex gap-2 text-text-muted text-sm">
              <span className="text-accent shrink-0">→</span>
              <span>{b}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Security warnings banner */}
      {hasFindings && (
        <div
          data-testid="security-warnings"
          className="border border-yellow-500/40 rounded-lg p-4 bg-yellow-500/5 space-y-3"
        >
          <p className="text-yellow-400 font-mono text-xs uppercase tracking-widest font-medium">
            Security Warnings ({findings.length})
          </p>
          <ul className="space-y-1.5">
            {findings.map((f, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className={`shrink-0 font-mono text-xs mt-0.5 ${
                  f.severity === "critical" ? "text-danger" : "text-yellow-400"
                }`}>
                  [{f.severity}]
                </span>
                <span className="text-text-muted">
                  Cell {f.cell_index}, line {f.line}: {f.description}
                </span>
              </li>
            ))}
          </ul>
          {!acknowledged && (
            <button
              data-testid="acknowledge-warnings-btn"
              onClick={() => setAcknowledged(true)}
              className="text-yellow-400 font-mono text-xs hover:text-yellow-300 transition-colors underline"
            >
              I understand the risks, show download options
            </button>
          )}
        </div>
      )}

      {/* Download / Colab buttons — hidden behind acknowledgement if findings exist */}
      {(!hasFindings || acknowledged) && (
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            data-testid="download-btn"
            onClick={handleDownload}
            className="flex-1 py-3 px-4 bg-accent text-surface rounded-lg font-mono text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            Download .ipynb
          </button>
          {colabUrl && (
            <a
              data-testid="colab-btn"
              href={colabUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-3 px-4 border border-border text-text-primary rounded-lg font-mono text-sm font-medium hover:border-accent/50 transition-colors text-center"
            >
              Open in Colab ↗
            </a>
          )}
        </div>
      )}

      {/* "Review warnings" button when findings exist but not yet acknowledged */}
      {hasFindings && !acknowledged && (
        <p className="text-text-muted font-mono text-xs text-center">
          Review security warnings above before downloading.
        </p>
      )}

      <button
        data-testid="reset-btn"
        onClick={onReset}
        className="w-full py-2 text-text-muted font-mono text-xs hover:text-text-primary transition-colors"
      >
        Generate Another →
      </button>
    </div>
  );
}
