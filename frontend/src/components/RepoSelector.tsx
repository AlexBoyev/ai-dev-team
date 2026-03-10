import { useState, useEffect, useCallback } from "react";
import {
  FolderGit2, Trash2, Download,
  ExternalLink, HardDrive, Calendar, Play, Loader,
} from "lucide-react";
import type { Repo } from "../types";
import { fetchRepos, deleteRepo, repoDownloadUrl } from "../api";

interface Props {
  selected: Repo | null;
  onSelect: (repo: Repo | null) => void;
  repoUrl: string;
  onRepoUrlChange: (v: string) => void;
  refreshTick: number;
  running: boolean;
  onRun: () => void;
}

function fmt(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function RepoSelector({
  selected, onSelect, repoUrl, onRepoUrlChange, refreshTick, running, onRun,
}: Props) {
  const [repos, setRepos]       = useState<Repo[]>([]);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await fetchRepos();
    setRepos(data);
    if (!selected && data.length > 0) onSelect(data[0]);
  }, []);

  useEffect(() => { load(); }, [refreshTick]);

  const handleSelect = (repo: Repo) => {
    onSelect(repo);
    onRepoUrlChange(repo.url ?? "");
  };

  const handleDelete = async (e: React.MouseEvent, repo: Repo) => {
    e.stopPropagation();
    if (!confirm(`Delete "${repo.name}" from workspace?\n\nThis removes all cloned files from disk.`)) return;
    setDeleting(repo.id);
    await deleteRepo(repo.id);
    if (selected?.id === repo.id) {
      onSelect(null);
      onRepoUrlChange("");
    }
    await load();
    setDeleting(null);
  };

  const handleDownload = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    window.location.href = repoDownloadUrl(id);
  };

  return (
    <div className="card repo-selector">
      <div className="card-header">
        <span className="card-title">
          <FolderGit2 size={15} /> Repositories
          <span style={{ fontWeight: 400, color: "var(--text-soft)", fontSize: 12 }}>
            &nbsp;({repos.length})
          </span>
        </span>
      </div>

      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>

        {/* URL input + Run button */}
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            className="repo-input"
            placeholder="https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => onRepoUrlChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !running && onRun()}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={onRun}
            disabled={running || !repoUrl.trim()}
            style={{ whiteSpace: "nowrap" }}
          >
            {running
              ? <><Loader size={13} className="spinning" /> Running…</>
              : <><Play size={13} /> Run</>
            }
          </button>
        </div>

        {/* Repo chips */}
        {repos.length > 0 ? (
          <div className="repo-list">
            {repos.map((r) => (
              <div
                key={r.id}
                className={`repo-chip ${selected?.id === r.id ? "active" : ""}`}
                onClick={() => handleSelect(r)}
              >
                <span style={{ fontSize: 18 }}>📁</span>
                <div className="repo-chip-info">
                  <div className="repo-chip-name">{r.name}</div>
                  <div className="repo-chip-meta">
                    <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
                      <HardDrive size={10} /> {fmt(r.disk_bytes)}
                    </span>
                    <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
                      <Calendar size={10} />
                      {r.cloned_at ? new Date(r.cloned_at).toLocaleDateString() : "—"}
                    </span>
                    {r.url && (
                      <a
                        href={r.url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        style={{ display: "flex", alignItems: "center", gap: 3,
                                 color: "var(--primary)", textDecoration: "none", fontSize: 11 }}
                      >
                        <ExternalLink size={10} /> GitHub
                      </a>
                    )}
                  </div>
                </div>
                <div className="repo-chip-actions">
                  <button
                    className="icon-btn"
                    title="Download ZIP"
                    onClick={(e) => handleDownload(e, r.id)}
                  >
                    <Download size={13} />
                  </button>
                  <button
                    className="icon-btn icon-btn-danger"
                    title="Delete repo"
                    onClick={(e) => handleDelete(e, r)}
                    disabled={deleting === r.id}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty" style={{ padding: "8px 0" }}>
            No repos yet — enter a GitHub URL above and click Run
          </p>
        )}

      </div>
    </div>
  );
}
