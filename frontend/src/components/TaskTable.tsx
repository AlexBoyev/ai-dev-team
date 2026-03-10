import { useState, useEffect } from "react";
import { ListChecks } from "lucide-react";
import { fetchTasks } from "../api";
import type { Task } from "../types";

interface Props {
  runId: string | null;
  refreshTick: number;        // ← add
}

export default function TaskTable({ runId, refreshTick }: Props) {
  const [tasks, setTasks] = useState<Task[]>([]);

  useEffect(() => {
    if (!runId) { setTasks([]); return; }
    fetchTasks(runId).then(setTasks);
  }, [runId, refreshTick]);

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
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id}>
                  <td className="task-id">{t.id.slice(0, 8)}</td>
                  <td>{t.title}</td>
                  <td style={{ fontFamily: "var(--mono)", fontSize: 11 }}>
                    {t.assigned_agent}
                  </td>
                  <td>
                    <span className={`badge badge-${t.status}`}>
                      <span className={`dot ${t.status === "in_progress" ? "dot-pulse" : ""}`} />
                      {t.status}
                    </span>
                  </td>
                  <td
                    style={{
                      fontSize: 12,
                      color: "var(--text-soft)",
                      maxWidth: 220,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={t.result ?? ""}
                  >
                    {t.result ?? "—"}
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
