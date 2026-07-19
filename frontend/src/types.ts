export interface AppInfo {
  id: string;
  display_name: string;
  category: "console" | "external";
  description: string;
}

export interface TraceStats {
  total_events: number;
  kept: number;
  removed: number;
  reduction_pct: number;
  stage1_removed: number;
  stage2_removed: number;
  stage3_removed: number;
  layer_breakdown: Record<string, number>;
}

export interface TraceResult {
  app_id: string;
  mermaid: string;
  stats: TraceStats;
  warnings: string[];
  empty: boolean;
  duration_ms: number;
}

export interface Stages {
  stage1: boolean;
  stage2: boolean;
  stage3: boolean;
  stage4: boolean;
}
