import type { TraceStats } from "../types";

const LAYER_COLORS: Record<string, string> = {
  Presentation_Layer: "#f472b6",
  Logic_Layer: "#7dd3fc",
  Data_Layer: "#34d399",
  Participant: "#a78bfa",
  Script: "#94a3b8",
};

export function StatsPanel({ stats, durationMs }: { stats: TraceStats; durationMs: number }) {
  const stageRows = [
    { label: "Stage 1 · Utilities & libraries", value: stats.stage1_removed },
    { label: "Stage 2 · Deep implementation", value: stats.stage2_removed },
    { label: "Stage 3 · Internal (same-class)", value: stats.stage3_removed },
  ];
  const maxRemoved = Math.max(1, ...stageRows.map((r) => r.value));
  const layers = Object.entries(stats.layer_breakdown).sort((a, b) => b[1] - a[1]);

  return (
    <div className="stats">
      <div className="stats-hero">
        <div className="reduction">
          <span className="reduction-num">{stats.reduction_pct.toFixed(1)}%</span>
          <span className="reduction-label">noise removed</span>
        </div>
        <div className="counts">
          <div>
            <span className="count-num">{stats.total_events.toLocaleString()}</span>
            <span className="count-label">captured</span>
          </div>
          <span className="count-arrow">→</span>
          <div>
            <span className="count-num kept">{stats.kept.toLocaleString()}</span>
            <span className="count-label">kept</span>
          </div>
        </div>
      </div>

      <div className="stats-section">
        <h4>Removed per stage</h4>
        {stageRows.map((r) => (
          <div className="stage-bar-row" key={r.label}>
            <span className="stage-bar-label">{r.label}</span>
            <div className="stage-bar-track">
              <div className="stage-bar-fill" style={{ width: `${(r.value / maxRemoved) * 100}%` }} />
            </div>
            <span className="stage-bar-value">{r.value}</span>
          </div>
        ))}
      </div>

      {layers.length > 0 && (
        <div className="stats-section">
          <h4>Layer distribution (kept)</h4>
          <div className="layer-chips">
            {layers.map(([name, n]) => (
              <span className="layer-chip" key={name}>
                <span className="layer-dot" style={{ background: LAYER_COLORS[name] ?? "#94a3b8" }} />
                {name.replace(/_/g, " ")} · {n}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="stats-foot">traced in {durationMs.toFixed(0)} ms</div>
    </div>
  );
}
