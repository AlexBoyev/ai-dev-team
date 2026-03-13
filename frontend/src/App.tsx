import { useState, useEffect, useCallback, useRef } from "react";
import Header from "./components/Header";
import RepoSelector from "./components/RepoSelector";
import AgentsPanel from "./components/AgentsPanel";
import TaskTable from "./components/TaskTable";
import LogViewer from "./components/LogViewer";
import ArtifactViewer from "./components/ArtifactViewer";
import RunHistory from "./components/RunHistory";
import { fetchState, postRun, postReset } from "./api";
import type { AppState, Repo } from "./types";
import CostDashboard from "./components/CostDashboard";

const EMPTY_STATE: AppState = {
  run_in_progress: false,
  run_id:          null,
  agents:          [],
  tasks:           [],
  logs:            [],
};

function statesEqual(a: AppState, b: AppState): boolean {
  if (a.run_in_progress !== b.run_in_progress) return false;
  if (a.run_id          !== b.run_id)          return false;
  if (a.tasks.length    !== b.tasks.length)    return false;
  if (a.logs.length     !== b.logs.length)     return false;
  if (a.agents.length   !== b.agents.length)   return false;

  // Check if any task status/result changed
  for (let i = 0; i < a.tasks.length; i++) {
    const ta = a.tasks[i], tb = b.tasks[i];
    if (
      ta.id       !== tb.id     ||
      ta.status   !== tb.status ||
      ta.result   !== tb.result ||
      ta.approved !== tb.approved
    ) return false;
  }

  // Check if any agent status changed
  for (let i = 0; i < a.agents.length; i++) {
    const aa = a.agents[i], ab = b.agents[i];
    if (aa.status !== ab.status || aa.last_action !== ab.last_action) return false;
  }

  return true;
}

export default function App() {
  const [state, setState]               = useState<AppState>(EMPTY_STATE);
  const [repoUrl, setRepoUrl]           = useState("");
  const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null);
  const [error, setError]               = useState<string | null>(null);
  const [refreshTick, setRefreshTick]   = useState(0);
  const [lastRunId, setLastRunId]       = useState<string | null>(null);
  const intervalRef                     = useRef<ReturnType<typeof setInterval> | null>(null);
  const wasRunningRef                   = useRef(false);

  const activeRunId = selectedRepo?.last_run_id ?? lastRunId ?? state.run_id;

  const poll = useCallback(async () => {
    try {
      const s = await fetchState();

      // Preserve scroll position — only update state if something actually changed
      setState((prev) => {
        const justFinished = wasRunningRef.current && !s.run_in_progress;
        wasRunningRef.current = s.run_in_progress;

        if (justFinished) {
          setRefreshTick((t) => t + 1);
        }

        // Skip re-render entirely if nothing meaningful changed
        if (statesEqual(prev, s)) return prev;

        return s;
      });

      if (s.run_id) setLastRunId(s.run_id);
    } catch { /* network blip */ }
  }, []);

  useEffect(() => {
    poll();
    intervalRef.current = setInterval(poll, 4000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [poll]);

  const handleRun = async () => {
    const url = repoUrl.trim() || selectedRepo?.url || "";
    if (!url) { setError("Enter a GitHub repo URL first"); return; }
    setError(null);
    const res = await postRun(url);
    if (!res.ok) setError(res.error ?? "Failed to start run");
    else await poll();
  };

  const handleStop = async () => {
    await postReset();
    await poll();
    setRefreshTick((t) => t + 1);
  };

  const handleSelectRepo = (repo: Repo | null) => {
    setSelectedRepo(repo);
    if (repo?.url) {
      setRepoUrl(repo.url);
    } else {
      setRepoUrl("");
      setLastRunId(null);
    }
    setRefreshTick((t) => t + 1);
  };

  return (
    <div className="app">
      <Header running={state.run_in_progress} />

      <main className="main">
        <RepoSelector
          selected={selectedRepo}
          onSelect={handleSelectRepo}
          repoUrl={repoUrl}
          onRepoUrlChange={setRepoUrl}
          refreshTick={refreshTick}
          running={state.run_in_progress}
          onRun={handleRun}
          onStop={handleStop}
        />

        {error && (
          <div style={{
            gridColumn:   "1 / -1",
            background:   "#fef2f2",
            border:       "1px solid #fecaca",
            borderRadius: 8,
            padding:      "10px 16px",
            color:        "var(--danger)",
            fontSize:     13,
            display:      "flex",
            alignItems:   "center",
            justifyContent: "space-between",
          }}>
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              style={{ background: "none", border: "none", cursor: "pointer",
                       color: "var(--danger)", fontSize: 16 }}
            >×</button>
          </div>
        )}

        <div className="grid-left">
          <AgentsPanel agents={state.agents} />
          <CostDashboard refreshTick={refreshTick} />
          <RunHistory currentRunId={activeRunId} refreshTick={refreshTick} />
        </div>

        <div className="grid-right">
          <TaskTable
            runId={activeRunId}
            refreshTick={refreshTick}
            running={state.run_in_progress}
          />
          <LogViewer
            runId={activeRunId}
            refreshTick={refreshTick}
            running={state.run_in_progress}
          />
          <ArtifactViewer runId={activeRunId} refreshTick={refreshTick} />
        </div>
      </main>
    </div>
  );
}
