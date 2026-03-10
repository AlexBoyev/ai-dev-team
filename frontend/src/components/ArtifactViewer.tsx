import { useState, useEffect, useRef } from "react";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";
import { fetchArtifacts, fetchArtifactContent } from "../api";
import type { Artifact } from "../types";

interface Props {
  runId: string | null;
  refreshTick: number;
}

export default function ArtifactViewer({ runId, refreshTick }: Props) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [active, setActive]       = useState<string | null>(null);
  const [content, setContent]     = useState("");
  const [loading, setLoading]     = useState(false);
  const [expanded, setExpanded]   = useState(true);
  const prevRunId                 = useRef<string | null>(null);

  useEffect(() => {
    const runChanged = runId !== prevRunId.current;
    prevRunId.current = runId;

    // Only wipe state when switching repos, not on tick refresh
    if (runChanged) {
      setArtifacts([]);
      setActive(null);
      setContent("");
    }

    if (!runId) return;

    fetchArtifacts(runId).then((data) => {
      setArtifacts(data);
      // Set first tab only if nothing is active yet
      setActive((prev) => prev ?? (data.length > 0 ? data[0].name : null));
    });
  }, [runId, refreshTick]);

  useEffect(() => {
    if (!runId || !active) { setContent(""); return; }
    setLoading(true);
    fetchArtifactContent(runId, active)
      .then(setContent)
      .catch(() => setContent("Failed to load file content."))
      .finally(() => setLoading(false));
  }, [active, runId]);

  if (!runId || artifacts.length === 0) return null;

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">
          <FileText size={15} /> Artifacts
          <span style={{ fontWeight: 400, color: "var(--text-soft)", fontSize: 12 }}>
            &nbsp;({artifacts.length} files)
          </span>
        </span>
        <button
          className="icon-btn"
          onClick={() => setExpanded((v) => !v)}
          title={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </button>
      </div>

      {expanded && (
        <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>

          {/* File tabs */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {artifacts.map((a) => (
              <button
                key={a.name}
                onClick={() => setActive(a.name)}
                title={`${a.name} — ${(a.size_bytes / 1024).toFixed(1)} KB`}
                style={{
                  padding: "4px 10px",
                  fontSize: 12,
                  borderRadius: 20,
                  border: active === a.name ? "1.5px solid var(--primary)" : "1.5px solid var(--border)",
                  background: active === a.name ? "var(--primary)" : "transparent",
                  color: active === a.name ? "#fff" : "var(--text)",
                  cursor: "pointer",
                  fontFamily: "var(--mono)",
                  transition: "all 0.15s ease",
                }}
              >
                {a.name}
              </button>
            ))}
          </div>

          {/* File size hint */}
          {active && (
            <div style={{ fontSize: 11, color: "var(--text-soft)" }}>
              {active} &middot;&nbsp;
              {((artifacts.find((a) => a.name === active)?.size_bytes ?? 0) / 1024).toFixed(1)} KB
            </div>
          )}

          {/* Content */}
          {loading ? (
            <p style={{ fontSize: 12, color: "var(--text-soft)" }}>Loading...</p>
          ) : content ? (
            <pre style={{
              margin: 0, padding: "10px 12px", fontSize: 12, lineHeight: 1.6,
              overflowX: "auto", background: "var(--bg)", borderRadius: 6,
              border: "1px solid var(--border)", maxHeight: 400, overflowY: "auto",
              whiteSpace: "pre-wrap", wordBreak: "break-word",
            }}>
              {content}
            </pre>
          ) : (
            <p style={{ fontSize: 12, color: "var(--text-soft)" }}>
              Select a file above to view its contents
            </p>
          )}

        </div>
      )}
    </div>
  );
}
