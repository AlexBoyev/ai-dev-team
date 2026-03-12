import type { AppState, Repo, Run, Artifact, Task, LogEntry, CostData } from "./types";

const BASE = "";

// ── State ──────────────────────────────────────────────────────────────────────

export async function fetchState(): Promise<AppState> {
  const r = await fetch(`${BASE}/api/state`);
  return r.json();
}

// ── Run control ────────────────────────────────────────────────────────────────

export async function postRun(repoUrl: string): Promise<{ ok: boolean; error?: string }> {
  const r = await fetch(`${BASE}/api/run`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ repo_url: repoUrl }),
  });
  return r.json();
}

export async function postReset(): Promise<void> {
  await fetch(`${BASE}/api/reset`, { method: "POST" });
}

// ── Phase 3: human approval ────────────────────────────────────────────────────

export async function postApprove(runId: string): Promise<{ ok: boolean; approved: boolean }> {
  const r = await fetch(`${BASE}/api/runs/${runId}/approve`, { method: "POST" });
  if (!r.ok) throw new Error(`Approve failed: ${r.status}`);
  return r.json();
}

export async function postReject(runId: string): Promise<{ ok: boolean; approved: boolean }> {
  const r = await fetch(`${BASE}/api/runs/${runId}/reject`, { method: "POST" });
  if (!r.ok) throw new Error(`Reject failed: ${r.status}`);
  return r.json();
}

// ── Repos ──────────────────────────────────────────────────────────────────────

export async function fetchRepos(): Promise<Repo[]> {
  const r = await fetch(`${BASE}/api/repos`);
  return r.json();
}

export async function deleteRepo(id: string): Promise<void> {
  await fetch(`${BASE}/api/repos/${id}`, { method: "DELETE" });
}

export function repoDownloadUrl(id: string): string {
  return `${BASE}/api/repos/${id}/download`;
}

export async function fetchRepoFiles(repoId: string): Promise<{ path: string; size_bytes: number }[]> {
  const r = await fetch(`${BASE}/api/repos/${repoId}/files`);
  if (!r.ok) return [];
  return r.json();
}

// ── Runs ───────────────────────────────────────────────────────────────────────

export async function fetchRuns(limit = 20): Promise<Run[]> {
  const r = await fetch(`${BASE}/api/runs?limit=${limit}`);
  return r.json();
}

// ── Tasks ──────────────────────────────────────────────────────────────────────

export async function fetchTasks(runId: string): Promise<Task[]> {
  const r = await fetch(`${BASE}/api/tasks/${runId}`);
  if (!r.ok) return [];
  return r.json();
}

// ── Logs ───────────────────────────────────────────────────────────────────────

export async function fetchLogs(runId: string): Promise<LogEntry[]> {
  const r = await fetch(`${BASE}/api/logs/${runId}`);
  if (!r.ok) return [];
  return r.json();
}

// ── Artifacts ──────────────────────────────────────────────────────────────────

export async function fetchArtifacts(runId: string): Promise<Artifact[]> {
  const r = await fetch(`${BASE}/api/artifacts/${runId}`);
  return r.json();
}

export async function fetchArtifactContent(
  runId: string,
  name: string,
): Promise<{ name: string; content: string }> {
  const r = await fetch(`${BASE}/api/artifacts/${runId}/${name}`);
  if (!r.ok) throw new Error(`Failed to load artifact: ${r.status}`);
  return r.json();
}

// ── Costs ──────────────────────────────────────────────────────────────────────

export async function fetchCosts(): Promise<CostData> {
  const r = await fetch(`${BASE}/api/costs`);
  return r.json();
}

export async function refreshPricing(): Promise<{ ok: boolean; models_loaded: number }> {
  const r = await fetch(`${BASE}/api/costs/refresh-pricing`, { method: "POST" });
  if (!r.ok) throw new Error(`Refresh pricing failed: ${r.status}`);
  return r.json();
}
