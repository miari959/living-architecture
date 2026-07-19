import type { AppInfo } from "../types";

interface Props {
  apps: AppInfo[];
  selected: string | null;
  onSelect: (id: string) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  console: "Hand-crafted demos",
  external: "Real-world projects",
};

export function AppPicker({ apps, selected, onSelect }: Props) {
  const groups: Record<string, AppInfo[]> = {};
  for (const a of apps) (groups[a.category] ??= []).push(a);

  return (
    <div className="app-picker">
      {Object.entries(groups).map(([cat, list]) => (
        <div key={cat} className="app-group">
          <h3 className="app-group-title">{CATEGORY_LABELS[cat] ?? cat}</h3>
          <div className="app-cards">
            {list.map((a) => (
              <button
                key={a.id}
                className={"app-card" + (selected === a.id ? " selected" : "")}
                onClick={() => onSelect(a.id)}
              >
                <span className="app-card-name">{a.display_name}</span>
                <span className="app-card-desc">{a.description}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
