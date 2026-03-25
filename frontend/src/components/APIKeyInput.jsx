import React, { useState } from "react";

export default function APIKeyInput({ value, onChange }) {
  const [visible, setVisible] = useState(false);

  return (
    <div data-testid="api-key-input-container" className="space-y-2">
      <label className="block text-sm font-medium text-text-muted font-mono uppercase tracking-widest">
        OpenAI API Key
      </label>
      <div className="relative">
        <input
          data-testid="api-key-input"
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="sk-..."
          className="w-full bg-surface-2 border border-border rounded-lg px-4 py-3 pr-24 text-text-primary font-mono text-sm focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors placeholder-text-muted/40"
        />
        <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
          <button
            data-testid="toggle-key-visibility"
            type="button"
            onClick={() => setVisible(!visible)}
            className="text-text-muted hover:text-text-primary transition-colors text-xs font-mono"
          >
            {visible ? "hide" : "show"}
          </button>
        </div>
      </div>
      <p className="text-xs text-text-muted flex items-center gap-1.5">
        <span>🔒</span>
        <span>Your key is never stored — used only for this session</span>
      </p>
    </div>
  );
}
