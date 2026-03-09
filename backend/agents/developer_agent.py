from __future__ import annotations

from typing import Any, Dict, List

from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class DeveloperAgent(BaseAgent):
    IGNORED_DIR_NAMES = {
        ".git",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        "venv",
        ".idea",
        ".vscode",
        "coverage",
        "out",
        "target",
        "bin",
        "obj",
    }

    BLOCKED_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".mp3",
        ".wav",
        ".ogg",
        ".mp4",
        ".avi",
        ".mov",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".rar",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".pdf",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".pack",
        ".idx",
        ".bin",
    }

    ALLOWED_EXTENSIONS = {
        ".py",
        ".md",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".html",
        ".css",
        ".scss",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
        ".txt",
        ".xml",
        ".java",
        ".kt",
        ".kts",
        ".go",
        ".rs",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".php",
        ".rb",
        ".sh",
        ".bat",
        ".ps1",
        ".env",
    }

    PREFERRED_NAMES = {
        "README.md",
        "README.txt",
        "main.py",
        "app.py",
        "index.html",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Makefile",
    }

    MAX_SELECTED_FILES = 10
    MAX_SUMMARY_CHARS = 4000

    def __init__(self, agent_id: str = "dev_1") -> None:
        super().__init__(
            AgentProfile(
                agent_id=agent_id,
                display_name="Developer",
                role="Developer",
            )
        )

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        target_subdir = str(payload.get("target_subdir", "")).strip()

        if task_name == "inventory_workspace":
            files = self._tool(ctx, "list_workspace_files_in_dir", relative_dir=target_subdir)
            metadata = self._tool(ctx, "get_workspace_file_metadata", relative_dir=target_subdir)

            filtered_files = [path for path in files if self._is_candidate_path(path)]
            filtered_metadata = [
                item for item in metadata
                if self._is_candidate_path(str(item.get("path", "")))
            ]

            return {
                "workspace_files": filtered_files,
                "workspace_metadata": filtered_metadata,
                "target_subdir": target_subdir,
                "result_message": f"Indexed {len(filtered_files)} files",
            }

        if task_name == "select_key_files":
            metadata = payload.get("workspace_metadata", [])
            selected = self._select_key_files(metadata)

            return {
                "selected_files": selected,
                "result_message": f"Selected {len(selected)} key files",
            }

        if task_name == "summarize_key_files":
            selected_files = payload.get("selected_files", [])
            summaries: List[Dict[str, str]] = []
            skipped_files: List[Dict[str, str]] = []

            for rel_path in selected_files:
                if not self._is_candidate_path(rel_path):
                    skipped_files.append(
                        {
                            "path": rel_path,
                            "reason": "Filtered out as non-source or ignored path",
                        }
                    )
                    continue

                try:
                    content = self._tool(ctx, "read_workspace_file", relative_path=rel_path)
                except Exception as e:
                    skipped_files.append(
                        {
                            "path": rel_path,
                            "reason": str(e),
                        }
                    )
                    continue

                summary = self._summarize_text(rel_path, content[: self.MAX_SUMMARY_CHARS])
                summaries.append(
                    {
                        "path": rel_path,
                        "summary": summary,
                    }
                )

            lines = [
                "# Code Summary",
                "",
                f"Target subdir: `{target_subdir or '.'}`",
                "",
            ]

            for item in summaries:
                lines.extend(
                    [
                        f"## {item['path']}",
                        "",
                        item["summary"],
                        "",
                    ]
                )

            if skipped_files:
                lines.extend(
                    [
                        "## Skipped files",
                        "",
                    ]
                )
                for item in skipped_files:
                    lines.append(f"- `{item['path']}`: {item['reason']}")
                lines.append("")

            return {
                "file_summaries": summaries,
                "skipped_files": skipped_files,
                "code_summary_md": "\n".join(lines),
                "result_message": (
                    f"Summarized {len(summaries)} files"
                    + (
                        f", skipped {len(skipped_files)} unreadable/non-source files"
                        if skipped_files
                        else ""
                    )
                ),
            }

        if task_name == "scan_and_report":
            scan_result = self._tool(ctx, "scan_workspace_in_dir", relative_dir=target_subdir)
            report_md = self._tool(ctx, "build_scan_report_md", scan_result=scan_result)
            report_md = "\n".join(
                [
                    "# Repository Report",
                    "",
                    f"Target subdir: `{target_subdir or '.'}`",
                    "",
                    report_md,
                ]
            )
            return {
                "scan_result": scan_result,
                "report_md": report_md,
                "result_message": "Scan complete",
            }

        raise ValueError(f"DeveloperAgent: unknown task_name={task_name}")

    def _select_key_files(self, metadata: List[Dict[str, Any]]) -> List[str]:
        filtered: List[tuple[int, str]] = []

        for item in metadata:
            path = str(item.get("path", ""))
            if not self._is_candidate_path(path):
                continue

            size = int(item.get("size", 0))
            filename = path.split("/")[-1]
            ext = self._get_extension(filename)

            score = 0

            if filename in self.PREFERRED_NAMES:
                score += 100

            if ext in self.ALLOWED_EXTENSIONS:
                score += 30

            if "/src/" in f"/{path}/":
                score += 20

            if "/backend/" in f"/{path}/" or "/frontend/" in f"/{path}/":
                score += 15

            if "/tests/" in f"/{path}/" or path.startswith("tests/"):
                score += 10

            if size > 0:
                score += min(size // 200, 25)

            if size > 200_000:
                score -= 40

            if score > 0:
                filtered.append((score, path))

        filtered.sort(key=lambda x: (-x[0], x[1]))
        return [path for _, path in filtered[: self.MAX_SELECTED_FILES]]

    def _summarize_text(self, rel_path: str, content: str) -> str:
        lines = content.splitlines()
        preview = lines[:20]
        non_empty = [line.strip() for line in lines if line.strip()]
        first_meaningful = non_empty[:5]

        summary_lines = [
            f"- File: `{rel_path}`",
            f"- Approx lines: {len(lines)}",
            f"- Preview lines used: {len(preview)}",
        ]

        if first_meaningful:
            summary_lines.append("- Notable content:")
            for line in first_meaningful:
                summary_lines.append(f"  - {line[:140]}")
        else:
            summary_lines.append("- File appears mostly empty.")

        return "\n".join(summary_lines)

    def _is_candidate_path(self, path: str) -> bool:
        normalized = str(path).replace("\\", "/").strip()
        if not normalized:
            return False

        parts = [part for part in normalized.split("/") if part]
        if any(part in self.IGNORED_DIR_NAMES for part in parts):
            return False

        filename = parts[-1] if parts else normalized
        ext = self._get_extension(filename)

        if ext in self.BLOCKED_EXTENSIONS:
            return False

        if ext and ext not in self.ALLOWED_EXTENSIONS:
            return False

        return True

    def _get_extension(self, filename: str) -> str:
        if "." not in filename:
            return ""
        return "." + filename.split(".")[-1].lower()