import { useState, useEffect } from "react";
import { History } from "lucide-react";
import { fetchRuns } from "../api";
import type { Run } from "../types";

interface Props {
  currentRunId: string | null;
  refreshTick: number;
}

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function duration(started: string | null, finished: string | null): string {
  if (!started) return "—";
  if (!finished) return "running...";
  const s = Math.round(
    (new Date(finished).getTime() - new Date(started).getTime()) / 1000
  );
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function RunHistory({ currentRunId, refreshTick }: Props) {
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    fetchRuns(50).then(setRuns);
  }, [refreshTick]);

  const repoName = (url: string | null) =>
    url ? url.replace("https://github.com/", "").replace("http://github.com/", "") : "—";

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <History size={15} /> Run History
          <span style={{ fontWeight: 400, color: "var(--text-soft)", fontSize: 12 }}>
            &nbsp;({runs.length})
          </span>
        </span>
      </div>

      <div className="card-body" style={{ padding: 0 }}>
        {runs.length === 0 ? (
          <p className="empty">No runs yet</p>
        ) : (
          <table className="task-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Repo</th>
                <th>Status</th>
                <th>When</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}
                  style={{ background: r.id === currentRunId ? "#f0f7ff" : undefined }}>
                  <td className="task-id">{r.id.slice(0, 8)}</td>
                  <td style={{ fontSize: 12, color: "var(--text-soft)",
                               maxWidth: 160, overflow: "hidden",
                               textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {repoName(r.repo_url)}
                  </td>
                  <td>
                    <span className={`badge badge-${r.status}`}>
                      <span className={`dot ${r.status === "running" ? "dot-pulse" : ""}`} />
                      {r.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text-soft)" }}>
                    {timeAgo(r.started_at)}
                  </td>
                  <td style={{ fontSize: 11, color: "var(--text-soft)" }}>
                    {duration(r.started_at, r.finished_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
