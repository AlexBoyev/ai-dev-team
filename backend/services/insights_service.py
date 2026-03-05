from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.services.scanner_service import EXCLUDE_DIRS


SUSPICIOUS_PATTERNS = (
    "api_key",
    "secret",
    "password",
    "token",
    "private_key",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
)

NOTE_PATTERNS = ("TODO", "FIXME", "HACK")


@dataclass(frozen=True)
class InsightsResult:
    todo_hits: int
    suspicious_hits: int
    largest_files: list[tuple[str, int]]  # (relative_path, bytes)
    todo_samples: list[str]
    suspicious_samples: list[str]


def _safe_read_text(path: Path, max_bytes: int = 200_000) -> str:
    """
    Read up to max_bytes, ignore decode errors.
    """
    with path.open("rb") as f:
        raw = f.read(max_bytes)
    return raw.decode("utf-8", errors="ignore")


def analyze_workspace(root: Path, max_samples: int = 25) -> InsightsResult:
    root = root.resolve()

    todo_hits = 0
    suspicious_hits = 0
    todo_samples: list[str] = []
    suspicious_samples: list[str] = []

    largest_files: list[tuple[str, int]] = []

    if not root.exists():
        return InsightsResult(0, 0, [], [], [])

    # Find largest files (fast)
    sizes: list[tuple[str, int]] = []
    for p in root.rglob("*"):
        parts = set(p.parts)
        if any(x in parts for x in EXCLUDE_DIRS):
            continue
        if p.is_file():
            try:
                sizes.append((str(p.relative_to(root)), p.stat().st_size))
            except OSError:
                continue
    sizes.sort(key=lambda x: x[1], reverse=True)
    largest_files = sizes[:8]

    # Search text-ish files for TODO/FIXME/HACK and suspicious strings
    for rel_path, _size in sizes:
        p = root / rel_path
        # only scan small/medium files for content
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".exe", ".dll"):
            continue
        try:
            text = _safe_read_text(p)
        except OSError:
            continue

        upper = text.upper()
        lower = text.lower()

        # TODO hits
        for pat in NOTE_PATTERNS:
            if pat in upper:
                count = upper.count(pat)
                todo_hits += count
                if len(todo_samples) < max_samples:
                    todo_samples.append(f"{rel_path} -> {pat} (x{count})")

        # suspicious hits (lowercase compare)
        for pat in SUSPICIOUS_PATTERNS:
            key = pat.lower()
            if key in lower:
                count = lower.count(key)
                suspicious_hits += count
                if len(suspicious_samples) < max_samples:
                    suspicious_samples.append(f"{rel_path} -> {pat} (x{count})")

    return InsightsResult(
        todo_hits=todo_hits,
        suspicious_hits=suspicious_hits,
        largest_files=largest_files,
        todo_samples=todo_samples,
        suspicious_samples=suspicious_samples,
    )


def append_insights_to_report(report_md: str, insights: InsightsResult) -> str:
    lines = [report_md.rstrip(), ""]
    lines.append("## Insights")
    lines.append(f"- Notes (TODO/FIXME/HACK): **{insights.todo_hits}**")
    lines.append(f"- Suspicious strings (api_key/secret/token/...): **{insights.suspicious_hits}**")
    lines.append("")
    lines.append("### Largest files")
    if not insights.largest_files:
        lines.append("- (none)")
    else:
        for p, sz in insights.largest_files:
            lines.append(f"- `{p}` — **{sz} bytes**")
    lines.append("")
    lines.append("### Note samples")
    if not insights.todo_samples:
        lines.append("- (none)")
    else:
        for s in insights.todo_samples:
            lines.append(f"- {s}")
    lines.append("")
    lines.append("### Suspicious samples")
    if not insights.suspicious_samples:
        lines.append("- (none)")
    else:
        for s in insights.suspicious_samples:
            lines.append(f"- {s}")
    lines.append("")
    return "\n".join(lines)