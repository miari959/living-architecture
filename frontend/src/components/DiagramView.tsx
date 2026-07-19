import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  themeVariables: {
    darkMode: true,
    background: "transparent",
    primaryColor: "#1b2130",
    primaryBorderColor: "#3b82f6",
    primaryTextColor: "#e6edf3",
    lineColor: "#7dd3fc",
    actorBkg: "#132033",
    actorBorder: "#3b82f6",
    signalColor: "#cbd5e1",
    signalTextColor: "#e6edf3",
  },
  sequence: { useMaxWidth: false, mirrorActors: false, wrap: false },
});

interface Props {
  mermaidText: string;
  empty: boolean;
  loading: boolean;
}

export function DiagramView({ mermaidText, empty, loading }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    if (empty || !mermaidText.trim()) {
      if (hostRef.current) hostRef.current.innerHTML = "";
      return;
    }
    const id = "mmd-" + Math.random().toString(36).slice(2);
    mermaid
      .render(id, mermaidText)
      .then(({ svg }) => {
        if (!cancelled && hostRef.current) hostRef.current.innerHTML = svg;
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message ?? "Failed to render diagram");
      });
    return () => {
      cancelled = true;
    };
  }, [mermaidText, empty]);

  return (
    <div className="diagram-wrap">
      <div className="diagram-toolbar">
        <button onClick={() => setZoom((z) => Math.min(3, z + 0.15))} aria-label="Zoom in">＋</button>
        <button onClick={() => setZoom((z) => Math.max(0.35, z - 0.15))} aria-label="Zoom out">－</button>
        <button onClick={() => setZoom(1)} aria-label="Reset zoom">reset</button>
        <span className="zoom-label">{Math.round(zoom * 100)}%</span>
      </div>

      <div className="diagram-canvas">
        {loading && <div className="diagram-hint">Tracing…</div>}
        {!loading && empty && (
          <div className="diagram-empty">
            <strong>No architectural interactions survived this filter.</strong>
            <p>
              Every captured call was filtered out at this stage combination. Turn
              off later stages (or Stage 2 / Stage 3) to see more of the raw trace.
            </p>
          </div>
        )}
        {!loading && error && (
          <div className="diagram-empty diagram-error">
            <strong>Diagram error</strong>
            <p>{error}</p>
          </div>
        )}
        <div
          ref={hostRef}
          className="diagram-svg"
          style={{ transform: `scale(${zoom})`, display: loading || empty || error ? "none" : "block" }}
        />
      </div>
    </div>
  );
}
