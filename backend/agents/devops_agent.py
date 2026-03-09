from __future__ import annotations

from typing import Dict

from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class DevOpsAgent(BaseAgent):
    def __init__(self, agent_id: str = "devops") -> None:
        super().__init__(
            AgentProfile(
                agent_id=agent_id,
                display_name="DevOps",
                role="DevOps",
            )
        )

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, object]) -> Dict[str, object]:
        if task_name == "write_artifacts":
            report_md = str(payload.get("report_md", ""))
            code_summary_md = str(payload.get("code_summary_md", ""))
            qa_findings_md = str(payload.get("qa_findings_md", ""))
            review_md = str(payload.get("review_md", ""))
            workspace_files = payload.get("workspace_files", [])
            selected_files = payload.get("selected_files", [])
            target_subdir = str(payload.get("target_subdir", "")).strip()

            if report_md:
                self._tool(ctx, "write_workspace_file", relative_path="report.md", content=report_md)

            if code_summary_md:
                self._tool(ctx, "write_workspace_file", relative_path="code_summary.md", content=code_summary_md)

            if qa_findings_md:
                self._tool(ctx, "write_workspace_file", relative_path="qa_findings.md", content=qa_findings_md)

            if review_md:
                self._tool(ctx, "write_workspace_file", relative_path="review.md", content=review_md)

            self._tool(ctx, "write_workspace_json", relative_path="repo_inventory.json", data=workspace_files)
            self._tool(ctx, "write_workspace_json", relative_path="selected_files.json", data=selected_files)

            final_summary = "\n".join(
                [
                    "# Final Summary",
                    "",
                    f"Target subdir: `{target_subdir or '.'}`",
                    "",
                    "Generated artifacts:",
                    "- report.md",
                    "- code_summary.md",
                    "- qa_findings.md",
                    "- review.md",
                    "- repo_inventory.json",
                    "- selected_files.json",
                ]
            )

            self._tool(ctx, "write_workspace_file", relative_path="final_summary.md", content=final_summary)

            return {
                "written": "workspace artifacts updated",
                "final_summary_md": final_summary,
                "result_message": "Artifacts written",
            }
        if task_name == "clone_repository":
            repo_url = payload["repo_url"]

            repo_path = self._tool(
                ctx,
                "clone_git_repo",
                repo_url=repo_url,
            )

            return {
                "repo_path": repo_path,
                "result_message": f"Repository cloned to {repo_path}",
            }
        raise ValueError(f"DevOpsAgent: unknown task_name={task_name}")