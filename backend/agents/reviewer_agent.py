from __future__ import annotations

from typing import Dict

from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class ReviewerAgent(BaseAgent):
    def __init__(self, agent_id: str = "reviewer") -> None:
        super().__init__(
            AgentProfile(
                agent_id=agent_id,
                display_name="Reviewer",
                role="Reviewer",
            )
        )

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, object]) -> Dict[str, object]:
        if task_name == "review_outputs":
            report_md = str(payload.get("report_md", ""))
            code_summary_md = str(payload.get("code_summary_md", ""))
            qa_findings_md = str(payload.get("qa_findings_md", ""))
            target_subdir = str(payload.get("target_subdir", "")).strip()

            notes = [
                "# Review",
                "",
                f"Target subdir: `{target_subdir or '.'}`",
                "",
                "## Output quality check",
                f"- Base report present: {'yes' if report_md.strip() else 'no'}",
                f"- Code summary present: {'yes' if code_summary_md.strip() else 'no'}",
                f"- QA findings present: {'yes' if qa_findings_md.strip() else 'no'}",
                "",
                "## Review notes",
            ]

            if report_md.strip():
                notes.append("- Repository structure report was generated.")
            else:
                notes.append("- Repository structure report is missing.")

            if code_summary_md.strip():
                notes.append("- File-level summaries were generated.")
            else:
                notes.append("- File-level summaries are missing.")

            if qa_findings_md.strip():
                notes.append("- QA findings were generated.")
            else:
                notes.append("- QA findings are missing.")

            if "Missing README: yes" in qa_findings_md:
                notes.append("- Repository may need a README for better onboarding.")

            if "Sparse test signal: yes" in qa_findings_md:
                notes.append("- Test presence appears weak or absent.")

            notes.extend(
                [
                    "",
                    "## Recommendation",
                    "- Next step: add remediation suggestions and per-file action items.",
                ]
            )

            return {
                "review_md": "\n".join(notes),
                "result_message": "Review complete",
            }

        raise ValueError(f"ReviewerAgent: unknown task_name={task_name}")