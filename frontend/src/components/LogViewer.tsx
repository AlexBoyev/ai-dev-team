import { useState, useEffect, useRef } from "react";
import { Terminal } from "lucide-react";
import { fetchLogs } from "../api";
import type { LogEntry } from "../types";

interface Props {
  runId: string | null;
  refreshTick: number;
}

function fmt(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString();
}

const LEVEL_COLORS: Record<string, { bg: string; color: string }> = {
  INFO:    { bg: "#dbeafe", color: "#1d4ed8" },
  WARNING: { bg: "#fef9c3", color: "#a16207" },
  WARN:    { bg: "#fef9c3", color: "#a16207" },
  ERROR:   { bg: "#fee2e2", color: "#b91c1c" },
  DEBUG:   { bg: "#f3f4f6", color: "#6b7280" },
};

export default function LogViewer({ runId, refreshTick }: Props) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const bottomRef       = useRef<HTMLDivElement>(null);

  // Fetch logs when runId or refreshTick changes
  useEffect(() => {
    if (!runId) { setLogs([]); return; }
    fetchLogs(runId).then(setLogs);
  }, [runId, refreshTick]);

  // Scroll to bottom only when new logs arrive — no smooth to prevent twitch
  useEffect(() => {
    if (logs.length > 0) {
      bottomRef.current?.scrollIntoView({ behavior: "instant" as ScrollBehavior });
    }
  }, [logs.length]);

  const visible = [...logs].reverse().slice(0, 50);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <Terminal size={15} /> Live Logs
          <span style={{ fontWeight: 400, color: "var(--text-soft)", fontSize: 12 }}>
            &nbsp;{logs.length} lines
          </span>
        </span>
      </div>

      <div className="card-body log-body" style={{ padding: 0, maxHeight: 320, overflowY: "auto" }}>
        {visible.length === 0 ? (
          <p style={{ padding: "10px 14px", fontSize: 12, color: "var(--text-soft)" }}>
            No logs yet
          </p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <tbody>
              {visible.map((l, i) => {
                const lvl   = (l.level ?? "INFO").toUpperCase();
                const badge = LEVEL_COLORS[lvl] ?? LEVEL_COLORS.INFO;
                return (
                  <tr key={i} style={{ background: i % 2 === 0 ? "transparent" : "rgba(0,0,0,0.02)" }}>
                    <td style={{ padding: "5px 10px", whiteSpace: "nowrap",
                                 color: "var(--text-soft)", fontFamily: "var(--mono)",
                                 fontSize: 11, minWidth: 80 }}>
                      {fmt(l.ts)}
                    </td>
                    <td style={{ padding: "5px 6px", whiteSpace: "nowrap" }}>
                      <span style={{ background: badge.bg, color: badge.color,
                                     fontWeight: 600, fontSize: 10, padding: "2px 6px",
                                     borderRadius: 4, fontFamily: "var(--mono)",
                                     letterSpacing: "0.03em" }}>
                        {lvl}
                      </span>
                    </td>
                    <td style={{ padding: "5px 8px", whiteSpace: "nowrap",
                                 color: "var(--primary)", fontFamily: "var(--mono)",
                                 fontSize: 11, minWidth: 90 }}>
                      {l.source}
                    </td>
                    <td style={{ padding: "5px 10px 5px 0", color: "var(--text)",
                                 wordBreak: "break-word", lineHeight: 1.5 }}>
                      {l.message}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
