import { useEffect, useState } from "react";
import { fetchApps, runTrace } from "./api/client";
import type { AppInfo, Stages, TraceResult } from "./types";
import { AppPicker } from "./components/AppPicker";
import { FilterToggles } from "./components/FilterToggles";
import { DiagramView } from "./components/DiagramView";
import { StatsPanel } from "./components/StatsPanel";
import { ErrorBanner } from "./components/ErrorBanner";

const DEFAULT_STAGES: Stages = { stage1: true, stage2: true, stage3: true, stage4: true };

export function App() {
  const [apps, setApps] = useState<AppInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [stages, setStages] = useState<Stages>(DEFAULT_STAGES);
  const [result, setResult] = useState<TraceResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApps()
      .then((a) => {
        setApps(a);
        if (a.length) setSelected(a[0].id);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function run(appId: string, st: Stages) {
    setRunning(true);
    setError(null);
    try {
      setResult(await runTrace(appId, st));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  function onSelect(id: string) {
    setSelected(id);
    setResult(null);
    run(id, stages);
  }

  return (
    <div className="app-shell">
      <header className="masthead">
        <div className="masthead-title">
          <span className="logo-dot" />
          <div>
            <h1>Living Architecture</h1>
            <p>Recover a system's real architecture from its runtime behaviour.</p>
          </div>
        </div>
        <a
          className="masthead-link"
          href="https://github.com"
          target="_blank"
          rel="noreferrer"
        >
          about the thesis
        </a>
      </header>

      <ErrorBanner
        error={error}
        warnings={result?.warnings ?? []}
        onDismiss={() => setError(null)}
      />

      <main className="layout">
        <aside className="sidebar">
          <AppPicker apps={apps} selected={selected} onSelect={onSelect} />
          <FilterToggles
            stages={stages}
            onChange={setStages}
            onRun={() => selected && run(selected, stages)}
            running={running}
            canRun={!!selected}
          />
        </aside>

        <section className="stage">
          <DiagramView
            mermaidText={result?.mermaid ?? ""}
            empty={result?.empty ?? false}
            loading={running}
          />
        </section>

        <aside className="rail">
          {result ? (
            <StatsPanel stats={result.stats} durationMs={result.duration_ms} />
          ) : (
            <div className="rail-placeholder">
              Select an app and run a trace to see filtering statistics.
            </div>
          )}
        </aside>
      </main>
    </div>
  );
}
