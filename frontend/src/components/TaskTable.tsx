import { useState, useEffect, useRef } from "react";
import { ListChecks, CheckCircle, XCircle } from "lucide-react";
import { fetchTasks, postApprove, postReject } from "../api";
import type { Task } from "../types";

interface Props {
  runId:        string | null;
  refreshTick:  number;
  running:      boolean;
}

export default function TaskTable({ runId, refreshTick, running }: Props) {
  const [tasks,    setTasks]    = useState<Task[]>([]);
  const [voting,   setVoting]   = useState<string | null>(null); // task id being voted on
  const intervalRef             = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = () => {
    if (!runId) { setTasks([]); return; }
    fetchTasks(runId).then(setTasks).catch(() => {});
  };

  // Fetch on runId / refreshTick change
  useEffect(() => { load(); }, [runId, refreshTick]);

  // Poll every 2.5s while a run is active
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (running && runId) {
      intervalRef.current = setInterval(load, 2500);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [running, runId]);

  async function handleApprove(task: Task) {
    if (!runId) return;
    setVoting(task.id);
    try {
      await postApprove(runId);
      load();
    } catch (err) {
      console.error("Approve failed", err);
    } finally {
      setVoting(null);
    }
  }

  async function handleReject(task: Task) {
    if (!runId) return;
    setVoting(task.id);
    try {
      await postReject(runId);
      load();
    } catch (err) {
      console.error("Reject failed", err);
    } finally {
      setVoting(null);
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <ListChecks size={15} /> Tasks
          <span style={{ fontWeight: 400, color: "var(--text-soft)", fontSize: 12 }}>
            &nbsp;({tasks.length} total)
          </span>
        </span>
      </div>

      <div className="card-body" style={{ padding: 0 }}>
        {tasks.length === 0 ? (
          <p className="empty">No tasks yet</p>
        ) : (
          <table className="task-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Agent</th>
                <th>Status</th>
                <th>Iter</th>
                <th>Result</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => {
                const isPendingReview =
                  t.task_type === "review_diff" &&
                  t.approved === null &&
                  t.status !== "failed";

                const isVoting = voting === t.id;

                return (
                  <tr key={t.id}>
                    <td className="task-id">{t.id.slice(0, 8)}</td>
                    <td>{t.title}</td>
                    <td>
                      <span style={{ fontSize: 12, color: "var(--text-soft)" }}>
                        {t.assigned_agent}
                      </span>
                    </td>
                    <td>
                      <span className={`badge badge-${t.status}`}>
                        <span
                          className={`dot ${t.status === "in_progress" ? "dot-pulse" : ""}`}
                        />
                        {t.status}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: "var(--text-soft)", textAlign: "center" }}>
                      {t.iteration > 0 ? `#${t.iteration}` : "—"}
                    </td>
                    <td className="task-result">{t.result ?? "—"}</td>
                    <td>
                      {isPendingReview ? (
                        <span style={{ display: "flex", gap: 6 }}>
                          <button
                            className="btn btn-approve"
                            title="Approve this fix"
                            disabled={isVoting}
                            onClick={() => handleApprove(t)}
                            style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}
                          >
                            <CheckCircle size={13} />
                            {isVoting ? "..." : "Approve"}
                          </button>
                          <button
                            className="btn btn-reject"
                            title="Reject — trigger another iteration"
                            disabled={isVoting}
                            onClick={() => handleReject(t)}
                            style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12 }}
                          >
                            <XCircle size={13} />
                            {isVoting ? "..." : "Reject"}
                          </button>
                        </span>
                      ) : t.approved === true ? (
                        <span className="badge badge-done" style={{ fontSize: 11 }}>
                          ✓ Approved
                        </span>
                      ) : t.approved === false ? (
                        <span className="badge badge-failed" style={{ fontSize: 11 }}>
                          ✗ Rejected
                        </span>
                      ) : (
                        <span style={{ color: "var(--text-soft)", fontSize: 12 }}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
