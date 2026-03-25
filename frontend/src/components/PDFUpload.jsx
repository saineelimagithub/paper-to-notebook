import React, { useCallback, useState } from "react";

export default function PDFUpload({ onSubmit, apiKey, disabled }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === "application/pdf") setFile(dropped);
  }, []);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected?.type === "application/pdf") setFile(selected);
  };

  const handleSubmit = async () => {
    if (!file || !apiKey) return;
    const formData = new FormData();
    formData.append("api_key", apiKey);
    formData.append("file", file);
    onSubmit(formData);
  };

  const canSubmit = !!file && !!apiKey && !disabled;

  return (
    <div data-testid="pdf-upload-container" className="space-y-4">
      <label
        data-testid="drop-zone"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`block border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          dragging
            ? "border-accent bg-accent/5"
            : "border-border hover:border-accent/50 bg-surface-1"
        }`}
      >
        <input
          data-testid="file-input"
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          className="hidden"
        />
        {file ? (
          <div data-testid="file-info" className="space-y-1">
            <p className="text-text-primary font-mono text-sm">{file.name}</p>
            <p className="text-text-muted text-xs">
              {(file.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-text-muted text-sm">
              Drop a research paper PDF here
            </p>
            <p className="text-text-muted/50 text-xs font-mono">
              or click to browse
            </p>
          </div>
        )}
      </label>

      <button
        data-testid="generate-btn"
        onClick={handleSubmit}
        disabled={!canSubmit}
        className={`w-full py-3 px-6 rounded-lg font-mono text-sm font-medium transition-all ${
          canSubmit
            ? "bg-accent text-surface hover:bg-accent/90 glow-accent"
            : "bg-surface-2 text-text-muted cursor-not-allowed border border-border"
        }`}
      >
        {disabled ? "Generating..." : "Generate Notebook →"}
      </button>
    </div>
  );
}
