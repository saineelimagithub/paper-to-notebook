import React, { useEffect, useRef, useState } from "react";

export default function ProgressDisplay({ jobId, onDone, onError }) {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("connecting");
  const logRef = useRef(null);

  useEffect(() => {
    if (!jobId) return;
    const es = new EventSource(`/stream/${jobId}`);

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.type === "progress") {
        const mins = String(Math.floor(event.elapsed / 60)).padStart(2, "0");
        const secs = String(Math.floor(event.elapsed % 60)).padStart(2, "0");
        setMessages((prev) => [
          ...prev,
          { ts: `${mins}:${secs}`, text: event.message },
        ]);
        setStatus("running");
      } else if (event.type === "done") {
        setStatus("done");
        es.close();
        onDone(event);
      } else if (event.type === "error") {
        setStatus("error");
        es.close();
        onError(event.message);
      }
    };

    es.onerror = () => {
      setStatus("error");
      onError("Connection lost");
      es.close();
    };

    return () => es.close();
  }, [jobId]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div data-testid="progress-display" className="space-y-4">
      <div className="flex items-center gap-3">
        {status === "connecting" || status === "running" ? (
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-accent"></span>
          </span>
        ) : status === "done" ? (
          <span className="h-2.5 w-2.5 rounded-full bg-accent"></span>
        ) : (
          <span className="h-2.5 w-2.5 rounded-full bg-danger"></span>
        )}
        <span className="text-text-muted font-mono text-sm">
          {status === "connecting"
            ? "Connecting..."
            : status === "running"
            ? "Generating notebook..."
            : status === "done"
            ? "Complete"
            : "Error"}
        </span>
      </div>

      <div
        data-testid="log-window"
        ref={logRef}
        className="bg-surface-1 border border-border rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm space-y-1"
      >
        {messages.map((m, i) => (
          <div key={i} className="flex gap-3">
            <span className="text-accent shrink-0">[{m.ts}]</span>
            <span className="text-text-muted">{m.text}</span>
          </div>
        ))}
        {messages.length === 0 && (
          <span className="text-text-muted/40">Waiting for server...</span>
        )}
      </div>
    </div>
  );
}
