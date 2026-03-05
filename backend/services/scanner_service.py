from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path


EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}


@dataclass(frozen=True)
class ScanResult:
    root: str
    total_files: int
    total_dirs: int
    python_files: int
    top_folders: list[tuple[str, int]]
    python_samples: list[str]


def scan_directory(root: Path, max_python_samples: int = 30) -> ScanResult:
    root = root.resolve()

    total_files = 0
    total_dirs = 0
    python_files = 0

    folder_counter: Counter[str] = Counter()
    python_samples: list[str] = []

    if not root.exists():
        return ScanResult(str(root), 0, 0, 0, [], [])

    for p in root.rglob("*"):
        parts = set(p.parts)
        if any(x in parts for x in EXCLUDE_DIRS):
            continue

        if p.is_dir():
            total_dirs += 1
            continue

        if not p.is_file():
            continue

        total_files += 1

        rel = p.relative_to(root)
        folder_key = rel.parts[0] if len(rel.parts) > 1 else "."
        folder_counter[folder_key] += 1

        if p.suffix.lower() == ".py":
            python_files += 1
            if len(python_samples) < max_python_samples:
                python_samples.append(str(rel))

    return ScanResult(
        root=str(root),
        total_files=total_files,
        total_dirs=total_dirs,
        python_files=python_files,
        top_folders=folder_counter.most_common(8),
        python_samples=python_samples,
    )


def build_markdown_report(result: ScanResult) -> str:
    lines: list[str] = []
    lines.append("# Workspace Scan Report")
    lines.append("")
    lines.append(f"**Root:** `{result.root}`")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total files: **{result.total_files}**")
    lines.append(f"- Total dirs: **{result.total_dirs}**")
    lines.append(f"- Python files: **{result.python_files}**")
    lines.append("")
    lines.append("## Top folders by file count")
    if not result.top_folders:
        lines.append("- (no data)")
    else:
        for folder, count in result.top_folders:
            lines.append(f"- `{folder}`: **{count}** files")
    lines.append("")
    lines.append("## Sample Python files")
    if not result.python_samples:
        lines.append("- (none found)")
    else:
        for p in result.python_samples:
            lines.append(f"- `{p}`")
    lines.append("")
    return "\n".join(lines)