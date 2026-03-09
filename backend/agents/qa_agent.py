from __future__ import annotations

from typing import Any, Dict, List

from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class QaAgent(BaseAgent):
    def __init__(self, agent_id: str = "qa_1") -> None:
        super().__init__(
            AgentProfile(
                agent_id=agent_id,
                display_name="Tester",
                role="Tester",
            )
        )

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, object]) -> Dict[str, object]:
        target_subdir = str(payload.get("target_subdir", "")).strip()

        if task_name == "build_qa_findings":
            todos = self._tool(ctx, "search_workspace_text", pattern="TODO", relative_dir=target_subdir)
            fixmes = self._tool(ctx, "search_workspace_text", pattern="FIXME", relative_dir=target_subdir)
            hacks = self._tool(ctx, "search_workspace_text", pattern="HACK", relative_dir=target_subdir)
            api_keys = self._tool(ctx, "search_workspace_text", pattern="api_key", relative_dir=target_subdir)
            passwords = self._tool(ctx, "search_workspace_text", pattern="password", relative_dir=target_subdir)
            metadata = self._tool(ctx, "get_workspace_file_metadata", relative_dir=target_subdir)

            large_files = self._find_large_files(metadata)
            missing_readme = self._find_missing_readme(metadata)
            sparse_test_signal = self._find_sparse_tests(metadata)

            lines: List[str] = [
                "# QA Findings",
                "",
                f"Target subdir: `{target_subdir or '.'}`",
                "",
                "## Summary",
                f"- TODO count: {len(todos)}",
                f"- FIXME count: {len(fixmes)}",
                f"- HACK count: {len(hacks)}",
                f"- Possible API key references: {len(api_keys)}",
                f"- Possible password references: {len(passwords)}",
                f"- Large files flagged: {len(large_files)}",
                f"- Missing README: {'yes' if missing_readme else 'no'}",
                f"- Sparse test signal: {'yes' if sparse_test_signal else 'no'}",
                "",
                "## Findings",
                "",
                "### Large files",
            ]

            if large_files:
                for item in large_files[:10]:
                    lines.append(f"- `{item['path']}` — {item['size']} bytes")
            else:
                lines.append("- None")

            lines.extend(["", "### TODO/FIXME/HACK"])

            combined = [("TODO", todos), ("FIXME", fixmes), ("HACK", hacks)]
            has_combined = False
            for label, entries in combined:
                for item in entries[:10]:
                    has_combined = True
                    lines.append(f"- [{label}] `{item['path']}`:{item['line']} — {item['text']}")
            if not has_combined:
                lines.append("- None")

            lines.extend(["", "### Sensitive-looking strings"])

            sensitive = [("api_key", api_keys), ("password", passwords)]
            has_sensitive = False
            for label, entries in sensitive:
                for item in entries[:10]:
                    has_sensitive = True
                    lines.append(f"- [{label}] `{item['path']}`:{item['line']} — {item['text']}")
            if not has_sensitive:
                lines.append("- None")

            lines.extend(["", "### Structural notes"])
            lines.append(f"- Missing README: {'yes' if missing_readme else 'no'}")
            lines.append(f"- Sparse test signal: {'yes' if sparse_test_signal else 'no'}")

            return {
                "qa_findings_md": "\n".join(lines),
                "risk_findings": {
                    "todo": todos,
                    "fixme": fixmes,
                    "hack": hacks,
                    "api_key": api_keys,
                    "password": passwords,
                    "large_files": large_files,
                    "missing_readme": missing_readme,
                    "sparse_test_signal": sparse_test_signal,
                },
                "result_message": "QA findings generated",
            }

        raise ValueError(f"QaAgent: unknown task_name={task_name}")

    def _find_large_files(self, metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        large = [item for item in metadata if int(item.get("size", 0)) >= 20_000]
        large.sort(key=lambda x: (-int(x.get("size", 0)), str(x.get("path", ""))))
        return large

    def _find_missing_readme(self, metadata: List[Dict[str, Any]]) -> bool:
        paths = {str(item.get("path", "")).lower() for item in metadata}
        return "readme.md" not in {p.split("/")[-1] for p in paths}

    def _find_sparse_tests(self, metadata: List[Dict[str, Any]]) -> bool:
        paths = [str(item.get("path", "")).lower() for item in metadata]
        test_like = [p for p in paths if "test" in p]
        return len(test_like) == 0