import { useState, useEffect, useRef } from "react";
import { FileText, ChevronDown, ChevronUp, Copy, Check, Download } from "lucide-react";
import { fetchArtifacts, fetchArtifactContent } from "../api";
import JSZip from "jszip";
import type { Artifact } from "../types";

interface Props {
  runId: string | null;
  refreshTick: number;
}

export default function ArtifactViewer({ runId, refreshTick }: Props) {
  const [artifacts, setArtifacts]   = useState<Artifact[]>([]);
  const [active, setActive]         = useState<string | null>(null);
  const [content, setContent]       = useState("");
  const [loading, setLoading]       = useState(false);
  const [expanded, setExpanded]     = useState(true);
  const [copied, setCopied]         = useState(false);
  const [downloading, setDownloading] = useState(false);
  const prevRunId = useRef<string | null>(null);

  useEffect(() => {
    const runChanged = runId !== prevRunId.current;
    prevRunId.current = runId;
    if (runChanged) {
      setArtifacts([]);
      setActive(null);
      setContent("");
    }
    if (!runId) return;
    fetchArtifacts(runId).then((data) => {
      setArtifacts(data);
      setActive((prev) => prev ?? (data.length > 0 ? data[0].name : null));
    });
  }, [runId, refreshTick]);

  useEffect(() => {
    if (!runId || !active) { setContent(""); return; }
    setLoading(true);
    fetchArtifactContent(runId, active)
      .then((res) => setContent(res.content))
      .catch(() => setContent("Failed to load file content."))
      .finally(() => setLoading(false));
  }, [active, runId]);

  // Copy current artifact content to clipboard
  const handleCopy = async () => {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback for older browsers
      const ta = document.createElement("textarea");
      ta.value = content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };


const handleDownloadAll = async () => {
  if (!runId || artifacts.length === 0) return;
  setDownloading(true);
  try {
    const zip = new JSZip();
    for (const artifact of artifacts) {
      const res = await fetchArtifactContent(runId, artifact.name);
      zip.file(artifact.name, res.content);
    }
    const blob = await zip.generateAsync({ type: "blob" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `artifacts-${runId?.slice(0, 8)}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } finally {
    setDownloading(false);
  }
};


  if (!runId || artifacts.length === 0) return null;

  const activeSize = artifacts.find((a) => a.name === active)?.size_bytes ?? 0;

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FileText size={15} style={{ color: "var(--primary)" }} />
          <span style={{ fontWeight: 600, fontSize: 14 }}>Artifacts</span>
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>({artifacts.length} files)</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* Download All button */}
          <button
            onClick={handleDownloadAll}
            disabled={downloading}
            title="Download all artifacts"
            style={{
              display: "flex", alignItems: "center", gap: 4,
              padding: "4px 10px", fontSize: 12, borderRadius: 6,
              border: "1.5px solid var(--border)",
              background: "transparent", color: "var(--text)",
              cursor: downloading ? "not-allowed" : "pointer",
              opacity: downloading ? 0.6 : 1,
              transition: "all 0.15s ease",
            }}
          >
            <Download size={12} />
            {downloading ? "Downloading..." : "Download All"}
          </button>

          {/* Collapse toggle */}
          <button
            onClick={() => setExpanded((v) => !v)}
            title={expanded ? "Collapse" : "Expand"}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-muted)", padding: 2 }}
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div>
          {/* File tabs */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
            {artifacts.map((a) => (
              <button
                key={a.name}
                onClick={() => setActive(a.name)}
                title={`${a.name} — ${(a.size_bytes / 1024).toFixed(1)} KB`}
                style={{
                  padding: "4px 10px", fontSize: 12, borderRadius: 20,
                  border: active === a.name ? "1.5px solid var(--primary)" : "1.5px solid var(--border)",
                  background: active === a.name ? "var(--primary)" : "transparent",
                  color: active === a.name ? "#fff" : "var(--text)",
                  cursor: "pointer", fontFamily: "var(--mono)",
                  transition: "all 0.15s ease",
                }}
              >
                {a.name}
              </button>
            ))}
          </div>

          {/* File info bar + Copy button */}
          {active && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--mono)" }}>
                {active} · {(activeSize / 1024).toFixed(1)} KB
              </span>

              <button
                onClick={handleCopy}
                disabled={!content || loading}
                title="Copy content to clipboard"
                style={{
                  display: "flex", alignItems: "center", gap: 4,
                  padding: "3px 10px", fontSize: 12, borderRadius: 6,
                  border: "1.5px solid var(--border)",
                  background: copied ? "var(--primary)" : "transparent",
                  color: copied ? "#fff" : "var(--text)",
                  cursor: !content || loading ? "not-allowed" : "pointer",
                  opacity: !content || loading ? 0.5 : 1,
                  transition: "all 0.15s ease",
                }}
              >
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          )}

          {/* Content */}
          {loading ? (
            <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "20px 0", textAlign: "center" }}>Loading...</div>
          ) : content ? (
            <pre style={{
              background: "var(--bg)", borderRadius: 8, padding: 14,
              fontSize: 12, lineHeight: 1.6, overflowX: "auto",
              whiteSpace: "pre-wrap", wordBreak: "break-word",
              maxHeight: 500, overflowY: "auto",
              border: "1px solid var(--border)", margin: 0,
            }}>
              {content}
            </pre>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: 13, padding: "20px 0", textAlign: "center" }}>
              Select a file above to view its contents
            </div>
          )}
        </div>
      )}
    </div>
  );
}
