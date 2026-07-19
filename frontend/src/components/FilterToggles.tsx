import type { Stages } from "../types";

interface Props {
  stages: Stages;
  onChange: (s: Stages) => void;
  onRun: () => void;
  running: boolean;
  canRun: boolean;
}

const STAGE_META: { key: keyof Stages; label: string; hint: string }[] = [
  { key: "stage1", label: "Stage 1", hint: "Drop libraries & utility calls (fan-in/out)" },
  { key: "stage2", label: "Stage 2", hint: "Limit deep implementation detail (call depth)" },
  { key: "stage3", label: "Stage 3", hint: "Keep only cross-file / cross-class interactions" },
  { key: "stage4", label: "Stage 4", hint: "Classify surviving calls into layers" },
];

export function FilterToggles({ stages, onChange, onRun, running, canRun }: Props) {
  return (
    <div className="filters">
      <div className="filters-head">
        <h3>Filter pipeline</h3>
        <p>Toggle each stage, then run the trace to see the architecture distil.</p>
      </div>

      <div className="stage-toggles">
        {STAGE_META.map((s) => {
          const on = stages[s.key];
          return (
            <label key={s.key} className={"stage-toggle" + (on ? " on" : "")}>
              <input
                type="checkbox"
                checked={on}
                onChange={(e) => onChange({ ...stages, [s.key]: e.target.checked })}
              />
              <span className="stage-toggle-top">
                <span className="stage-toggle-label">{s.label}</span>
                <span className={"switch" + (on ? " on" : "")} aria-hidden />
              </span>
              <span className="stage-toggle-hint">{s.hint}</span>
            </label>
          );
        })}
      </div>

      <button className="run-btn" onClick={onRun} disabled={running || !canRun}>
        {running ? "Tracing…" : "Run trace"}
      </button>
    </div>
  );
}
