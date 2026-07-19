import type { AppInfo, Stages, TraceResult } from "../types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function fetchApps(): Promise<AppInfo[]> {
  return json<AppInfo[]>(await fetch("/api/apps"));
}

export async function runTrace(appId: string, stages: Stages): Promise<TraceResult> {
  const res = await fetch("/api/trace", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ app_id: appId, ...stages }),
  });
  return json<TraceResult>(res);
}
