import type { AppState, Repo, Run, Artifact, Task, LogEntry, CostData } from "./types";

const BASE = "";

export async function fetchState(): Promise<AppState> {
  const r = await fetch(`${BASE}/api/state`);
  return r.json();
}

export async function postRun(repoUrl: string): Promise<{ ok: boolean; error?: string }> {
  const r = await fetch(`${BASE}/api/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_url: repoUrl }),
  });
  return r.json();
}

export async function postReset(): Promise<void> {
  await fetch(`${BASE}/api/reset`, { method: "POST" });
}

export async function fetchRepos(): Promise<Repo[]> {
  const r = await fetch(`${BASE}/api/repos`);
  return r.json();
}

export async function deleteRepo(id: string): Promise<void> {
  await fetch(`${BASE}/api/repos/${id}`, { method: "DELETE" });
}

export async function fetchRuns(limit = 20): Promise<Run[]> {
  const r = await fetch(`${BASE}/api/runs?limit=${limit}`);
  return r.json();
}

export async function fetchTasks(runId: string): Promise<Task[]> {
  const r = await fetch(`${BASE}/api/tasks/${runId}`);
  if (!r.ok) return [];
  return r.json();
}

export async function fetchLogs(runId: string): Promise<LogEntry[]> {
  const r = await fetch(`${BASE}/api/logs/${runId}`);
  if (!r.ok) return [];
  return r.json();
}

export async function fetchArtifacts(runId: string): Promise<Artifact[]> {
  const r = await fetch(`${BASE}/api/artifacts/${runId}`);
  return r.json();
}

export async function fetchArtifactContent(runId: string, name: string): Promise<string> {
  const r = await fetch(`${BASE}/api/artifacts/${runId}/${name}`);
  const j = await r.json();
  return j.content ?? "";
}

export function repoDownloadUrl(id: string): string {
  return `${BASE}/api/repos/${id}/download`;
}

export async function fetchCosts(): Promise<CostData> {
  const r = await fetch(`${BASE}/api/costs`);
  return r.json();
}
