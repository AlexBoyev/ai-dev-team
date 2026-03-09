from __future__ import annotations

from typing import Any, Dict, List


from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class DeveloperAgent(BaseAgent):
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

            return {
                "workspace_files": files,
                "workspace_metadata": metadata,
                "target_subdir": target_subdir,
                "result_message": f"Indexed {len(files)} files",
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

            for rel_path in selected_files:
                content = self._tool(ctx, "read_workspace_file", relative_path=rel_path)
                summary = self._summarize_text(rel_path, content)
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

            return {
                "file_summaries": summaries,
                "code_summary_md": "\n".join(lines),
                "result_message": f"Summarized {len(summaries)} files",
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
        preferred_names = {
            "README.md",
            "main.py",
            "app.py",
            "index.html",
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Dockerfile",
        }
        allowed_exts = {".py", ".md", ".js", ".ts", ".html", ".css", ".json", ".yml", ".yaml"}

        filtered = []
        for item in metadata:
            path = str(item.get("path", ""))
            size = int(item.get("size", 0))
            filename = path.split("/")[-1]

            ext = ""
            if "." in filename:
                ext = "." + filename.split(".")[-1].lower()

            score = 0
            if filename in preferred_names:
                score += 100
            if ext in allowed_exts:
                score += 30
            if "/tests/" in f"/{path}/" or path.startswith("tests/"):
                score += 10
            if size > 0:
                score += min(size // 200, 25)

            if score > 0:
                filtered.append((score, path))

        filtered.sort(key=lambda x: (-x[0], x[1]))
        selected = [path for _, path in filtered[:10]]
        return selected

    def _summarize_text(self, rel_path: str, content: str) -> str:
        lines = content.splitlines()
        preview = lines[:20]

        non_empty = [line.strip() for line in lines if line.strip()]
        first_meaningful = non_empty[:5]

        summary_lines = [
            f"- Approx lines: {len(lines)}",
            f"- Preview lines used: {len(preview)}",
        ]

        if first_meaningful:
            summary_lines.append("- Notable content:")
            for line in first_meaningful:
                shortened = line[:140]
                summary_lines.append(f"  - {shortened}")
        else:
            summary_lines.append("- File appears mostly empty.")

        return "\n".join(summary_lines)