import { useState, useEffect, useRef } from "react";
import { ListChecks, CheckCircle, XCircle, ChevronDown, ChevronUp } from "lucide-react";
import { fetchTasks, postApprove, postReject, fetchArtifactContent } from "../api";
import type { Task } from "../types";

interface Props {
  runId:       string | null;
  refreshTick: number;
  running:     boolean;
}

interface TaskDetail {
  diff?:       string;
  testOutput?: string;
  loading:     boolean;
}

export default function TaskTable({ runId, refreshTick, running }: Props) {
  const [tasks,    setTasks]    = useState<Task[]>([]);
  const [voting,   setVoting]   = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [details,  setDetails]  = useState<Record<string, TaskDetail>>({});
  const intervalRef             = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = () => {
    if (!runId) { setTasks([]); return; }
    fetchTasks(runId).then(setTasks).catch(() => {});
  };

  useEffect(() => { load(); }, [runId, refreshTick]);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (running && runId) {
      intervalRef.current = setInterval(load, 2500);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [running, runId]);

  const handleExpand = async (task: Task) => {
    const isOpen = expanded === task.id;
    setExpanded(isOpen ? null : task.id);
    if (isOpen || !runId) return;

    const iteration = task.iteration ?? 1;

    // Already fetched — don't re-fetch
    if (details[task.id]) return;

    setDetails((prev) => ({ ...prev, [task.id]: { loading: true } }));

    if (task.task_type === "review_diff") {
      // Fetch diff + the matching test output for the same iteration
      const [diffRes, testRes] = await Promise.allSettled([
        fetchArtifactContent(runId, `fix_diff_iter${iteration}.diff`),
        fetchArtifactContent(runId, `test_results_iter${iteration}.txt`),
      ]);

      setDetails((prev) => ({
        ...prev,
        [task.id]: {
          loading:    false,
          diff:       diffRes.status === "fulfilled"  ? diffRes.value.content  : "No diff file found for this iteration.",
          testOutput: testRes.status === "fulfilled"  ? testRes.value.content  : undefined,
        },
      }));
      return;
    }

    if (task.task_type === "run_tests") {
      try {
        const res = await fetchArtifactContent(runId, `test_results_iter${iteration}.txt`);
        setDetails((prev) => ({ ...prev, [task.id]: { loading: false, testOutput: res.content } }));
      } catch {
        setDetails((prev) => ({ ...prev, [task.id]: { loading: false, testOutput: "No test output file found." } }));
      }
      return;
    }

    // Any other expandable task — just clear loading
    setDetails((prev) => ({ ...prev, [task.id]: { loading: false } }));
  };

  async function handleApprove(task: Task) {
    if (!runId) return;
    setVoting(task.id);
    try { await postApprove(runId); load(); }
    catch (err) { console.error("Approve failed", err); }
    finally { setVoting(null); }
  }

  async function handleReject(task: Task) {
    if (!runId) return;
    setVoting(task.id);
    try { await postReject(runId); load(); }
    catch (err) { console.error("Reject failed", err); }
    finally { setVoting(null); }
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

                const isVoting     = voting === t.id;
                const isExpanded   = expanded === t.id;
                const detail       = details[t.id];
                const isExpandable = !!t.result || t.task_type === "review_diff" || t.task_type === "run_tests";

                return (
                  <>
                    {/* ── Main row ── */}
                    <tr
                      key={t.id}
                      onClick={() => isExpandable && handleExpand(t)}
                      style={{ cursor: isExpandable ? "pointer" : "default" }}
                    >
                      <td className="task-id">{t.id.slice(0, 8)}</td>
                      <td>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          {t.title}
                          {isExpandable && (
                            isExpanded
                              ? <ChevronUp  size={13} style={{ color: "var(--text-soft)" }} />
                              : <ChevronDown size={13} style={{ color: "var(--text-soft)" }} />
                          )}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontSize: 12, color: "var(--text-soft)" }}>
                          {t.assigned_agent}
                        </span>
                      </td>
                      <td>
                        <span className={`badge badge-${t.status}`}>
                          <span className={`dot ${t.status === "in_progress" ? "dot-pulse" : ""}`} />
                          {t.status}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: "var(--text-soft)", textAlign: "center" }}>
                        {t.iteration > 0 ? `#${t.iteration}` : "—"}
                      </td>
                      <td className="task-result">{t.result ?? "—"}</td>
                      <td onClick={(e) => e.stopPropagation()}>
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
                          <span className="badge badge-done"   style={{ fontSize: 11 }}>✓ Approved</span>
                        ) : t.approved === false ? (
                          <span className="badge badge-failed" style={{ fontSize: 11 }}>✗ Rejected</span>
                        ) : (
                          <span style={{ color: "var(--text-soft)", fontSize: 12 }}>—</span>
                        )}
                      </td>
                    </tr>

                    {/* ── Expanded detail row ── */}
                    {isExpanded && (
                      <tr key={`${t.id}-detail`}>
                        <td colSpan={7} style={{ padding: 0, background: "var(--bg)" }}>
                          <div style={{
                            padding:      "12px 16px",
                            borderTop:    "1px solid var(--border)",
                            borderBottom: "1px solid var(--border)",
                          }}>

                            {/* ── Metadata strip ── */}
                            <div style={{
                              display: "flex", gap: 24, flexWrap: "wrap",
                              fontSize: 12, color: "var(--text-soft)", marginBottom: 10,
                            }}>
                              <span><b>Task ID:</b> {t.id}</span>
                              <span><b>Type:</b> {t.task_type}</span>
                              <span><b>Agent:</b> {t.assigned_agent}</span>
                              <span><b>Iteration:</b> {t.iteration > 0 ? `#${t.iteration}` : "—"}</span>
                              <span><b>Status:</b> {t.status}</span>
                            </div>

                            {/* ── Result message ── */}
                            {t.result && (
                              <div style={{ fontSize: 12, marginBottom: 10 }}>
                                <b>Result:</b> {t.result}
                              </div>
                            )}

                            {detail?.loading && (
                              <div style={{ fontSize: 12, color: "var(--text-soft)" }}>Loading...</div>
                            )}

                            {/* ── Test output (run_tests) ── */}
                            {!detail?.loading && t.task_type === "run_tests" && (
                              <TestOutputBlock
                                label={`Test Output — Iteration ${t.iteration}`}
                                content={detail?.testOutput}
                              />
                            )}

                            {/* ── review_diff: test summary + diff ── */}
                            {!detail?.loading && t.task_type === "review_diff" && (
                              <>
                                {/* Test result summary from same iteration */}
                                {detail?.testOutput && (
                                  <TestOutputBlock
                                    label={`Test Results — Iteration ${t.iteration}`}
                                    content={detail.testOutput}
                                  />
                                )}

                                {/* Diff viewer */}
                                <div style={{ marginTop: detail?.testOutput ? 14 : 0 }}>
                                  <div style={{
                                    fontSize: 12, fontWeight: 600, marginBottom: 6,
                                    color: "var(--text)",
                                  }}>
                                    Code Changes (Diff — Iteration {t.iteration})
                                  </div>
                                  <DiffBlock content={detail?.diff} />
                                </div>

                                {/* Approve / Reject inside drawer */}
                                {isPendingReview && (
                                  <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                                    <button
                                      className="btn btn-approve"
                                      disabled={isVoting}
                                      onClick={() => handleApprove(t)}
                                      style={{ display: "flex", alignItems: "center", gap: 4 }}
                                    >
                                      <CheckCircle size={13} />
                                      {isVoting ? "..." : "Approve this fix"}
                                    </button>
                                    <button
                                      className="btn btn-reject"
                                      disabled={isVoting}
                                      onClick={() => handleReject(t)}
                                      style={{ display: "flex", alignItems: "center", gap: 4 }}
                                    >
                                      <XCircle size={13} />
                                      {isVoting ? "..." : "Reject — try again"}
                                    </button>
                                  </div>
                                )}
                              </>
                            )}

                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function TestOutputBlock({ label, content }: { label: string; content?: string }) {
  if (!content) return null;

  const passed =
    content.includes("PASSED") ||
    content.includes("passed") ||
    content.includes("ok") ||
    content.includes("SUCCESS");

  const failed =
    content.includes("FAILED") ||
    content.includes("failed") ||
    content.includes("error") ||
    content.includes("ERROR");

  const statusColor = passed && !failed ? "#3fb950" : failed ? "#f85149" : "#e6edf3";

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{
        fontSize: 12, fontWeight: 600, marginBottom: 6,
        color: statusColor,
        display: "flex", alignItems: "center", gap: 6,
      }}>
        {passed && !failed ? "✓" : failed ? "✗" : "●"} {label}
      </div>
      <pre style={{
        background:   "#0d1117",
        color:        statusColor,
        borderRadius: 8,
        padding:      12,
        fontSize:     11,
        lineHeight:   1.6,
        overflowX:    "auto",
        whiteSpace:   "pre-wrap",
        wordBreak:    "break-word",
        maxHeight:    220,
        overflowY:    "auto",
        border:       "1px solid var(--border)",
        margin:       0,
      }}>
        {content}
      </pre>
    </div>
  );
}

function DiffBlock({ content }: { content?: string }) {
  if (!content) return <div style={{ fontSize: 12, color: "var(--text-soft)" }}>(no diff content)</div>;

  return (
    <pre style={{
      background:   "#0d1117",
      color:        "#e6edf3",
      borderRadius: 8,
      padding:      12,
      fontSize:     12,
      lineHeight:   1.6,
      overflowX:    "auto",
      whiteSpace:   "pre-wrap",
      wordBreak:    "break-word",
      maxHeight:    400,
      overflowY:    "auto",
      border:       "1px solid var(--border)",
      margin:       0,
    }}>
      {content.split("\n").map((line, i) => (
        <span
          key={i}
          style={{
            display: "block",
            color:
              line.startsWith("+")  ? "#3fb950" :
              line.startsWith("-")  ? "#f85149" :
              line.startsWith("@@") ? "#79c0ff" :
              "#e6edf3",
          }}
        >
          {line}
        </span>
      ))}
    </pre>
  );
}
