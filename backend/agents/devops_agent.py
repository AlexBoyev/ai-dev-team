from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

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

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:

        if task_name == "clone_repository":
            repo_url = str(payload.get("repo_url", "")).strip()
            if not repo_url:
                raise ValueError("DevOpsAgent: repo_url is required for clone_repository")

            repo_path = self._tool(ctx, "clone_git_repo", repo_url=repo_url)

            return {
                "repo_path": repo_path,
                "result_message": f"Repository cloned to {repo_path}",
            }

        if task_name == "write_artifacts":
            target_subdir   = str(payload.get("target_subdir", "")).strip()
            workspace_files = payload.get("workspace_files", []) or []
            selected_files  = payload.get("selected_files", []) or []
            report_md       = str(payload.get("report_md", ""))
            code_summary_md = str(payload.get("code_summary_md", ""))
            qa_findings_md  = str(payload.get("qa_findings_md", ""))
            review_md       = str(payload.get("review_md", ""))

            # ── Run-specific output folder ────────────────────────────────
            # orchestrator sets artifact_dir = workspace/runs/{run_id}/
            # We prefix every file path with it so runs never collide.
            artifact_dir = str(payload.get("artifact_dir", "")).strip()
            def _path(name: str) -> str:
                if artifact_dir:
                    return str(Path(artifact_dir) / name)
                return name  # fallback: flat workspace (old behaviour)

            final_summary_md = self._build_final_summary(
                target_subdir=target_subdir,
                workspace_files=workspace_files,
                selected_files=selected_files,
                report_md=report_md,
                code_summary_md=code_summary_md,
                qa_findings_md=qa_findings_md,
                review_md=review_md,
            )

            self._tool(ctx, "write_workspace_json", relative_path=_path("repo_inventory.json"), data=workspace_files)
            self._tool(ctx, "write_workspace_json", relative_path=_path("selected_files.json"),  data=selected_files)
            self._tool(ctx, "write_workspace_file", relative_path=_path("report.md"),            content=report_md)
            self._tool(ctx, "write_workspace_file", relative_path=_path("code_summary.md"),      content=code_summary_md)
            self._tool(ctx, "write_workspace_file", relative_path=_path("qa_findings.md"),       content=qa_findings_md)
            self._tool(ctx, "write_workspace_file", relative_path=_path("review.md"),            content=review_md)
            self._tool(ctx, "write_workspace_file", relative_path=_path("final_summary.md"),     content=final_summary_md)

            return {
                "final_summary_md": final_summary_md,
                "result_message": "Artifacts written",
            }

        raise ValueError(f"DevOpsAgent: unknown task_name={task_name}")

    def _build_final_summary(
        self,
        target_subdir: str,
        workspace_files: List[str],
        selected_files: List[str],
        report_md: str,
        code_summary_md: str,
        qa_findings_md: str,
        review_md: str,
    ) -> str:
        project_type    = self._extract_bullet_value(report_md, "Project type")
        languages       = self._extract_bullet_value(report_md, "Languages")
        frameworks      = self._extract_bullet_value(report_md, "Frameworks / tools")
        assets_detected = self._extract_bullet_value(report_md, "Assets detected")

        status       = self._extract_review_status(review_md)
        risks        = self._extract_review_concerns(review_md)
        next_actions = self._extract_numbered_section(review_md, "## Recommended next actions")
        reading_order = self._extract_numbered_section(report_md, "## Where to start reading")
        entrypoints  = self._extract_bulleted_section(report_md, "## Entrypoint candidates")
        run_hints    = self._extract_bulleted_section(report_md, "## How it likely runs")
        qa_risks     = self._extract_bulleted_section(qa_findings_md, "## Risks")
        qa_strengths = self._extract_bulleted_section(qa_findings_md, "## Strengths")

        lines = [
            "# Final Summary",
            "",
            f"Target subdir: `{target_subdir or '.'}`",
            "",
            "## Executive overview",
            "",
            f"- Review status: **{status or 'unknown'}**",
            f"- Candidate files indexed: {len(workspace_files)}",
            f"- Key files selected: {len(selected_files)}",
            f"- Project type: {project_type or 'Unknown'}",
            f"- Languages: {languages or 'Unknown'}",
            f"- Frameworks / tools: {frameworks or 'None detected'}",
            f"- Assets detected: {assets_detected or 'Unknown'}",
            "",
            "## How to approach this repository",
            "",
        ]

        if reading_order:
            lines.append("Recommended reading order:")
            lines.append("")
            for item in reading_order[:8]:
                lines.append(item)
        else:
            lines.append("- No reading order was extracted from the repository report.")

        lines.extend(["", "## Likely entrypoints", ""])
        if entrypoints:
            for item in entrypoints[:8]:
                lines.append(item)
        else:
            lines.append("- No clear entrypoints were identified.")

        lines.extend(["", "## Likely run/build hints", ""])
        if run_hints:
            for item in run_hints[:8]:
                lines.append(item)
        else:
            lines.append("- No reliable run/build hints were extracted.")

        lines.extend(["", "## QA highlights", ""])
        if qa_risks:
            lines.append("Risks:")
            lines.append("")
            for item in qa_risks[:8]:
                lines.append(item)
            lines.append("")
        else:
            lines.append("- No QA risks section found.")
            lines.append("")

        if qa_strengths:
            lines.append("Strengths:")
            lines.append("")
            for item in qa_strengths[:8]:
                lines.append(item)
            lines.append("")
        else:
            lines.append("- No QA strengths section found.")
            lines.append("")

        lines.extend(["## Review highlights", ""])
        if risks:
            for item in risks[:8]:
                lines.append(item)
        else:
            lines.append("- No major review concerns recorded.")

        lines.extend(["", "## Recommended next actions", ""])
        if next_actions:
            for item in next_actions[:8]:
                lines.append(item)
        else:
            lines.append("1. Strengthen repository intelligence and scaling rules for larger repositories.")

        lines.extend([
            "",
            "## Generated artifacts",
            "",
            "- `repo_inventory.json`",
            "- `selected_files.json`",
            "- `report.md`",
            "- `code_summary.md`",
            "- `qa_findings.md`",
            "- `review.md`",
            "- `final_summary.md`",
            "",
        ])

        return "\n".join(lines)

    def _extract_bullet_value(self, md: str, label: str) -> str:
        prefix = f"- {label}:"
        for line in md.splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                return stripped[len(prefix):].strip()
        return ""

    def _extract_review_status(self, md: str) -> str:
        prefix = "- Status:"
        for line in md.splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                return stripped[len(prefix):].replace("*", "").strip()
        return ""

    def _extract_bulleted_section(self, md: str, heading: str) -> List[str]:
        lines = md.splitlines()
        items: List[str] = []
        in_section = False
        for line in lines:
            stripped = line.strip()
            if stripped == heading:
                in_section = True
                continue
            if in_section and stripped.startswith("## "):
                break
            if in_section and stripped.startswith("- "):
                items.append(stripped)
        return items

    def _extract_numbered_section(self, md: str, heading: str) -> List[str]:
        lines = md.splitlines()
        items: List[str] = []
        in_section = False
        for line in lines:
            stripped = line.strip()
            if stripped == heading:
                in_section = True
                continue
            if in_section and stripped.startswith("## "):
                break
            if in_section and stripped and stripped[0].isdigit() and ". " in stripped:
                items.append(stripped)
        return items

    def _extract_review_concerns(self, md: str) -> List[str]:
        return self._extract_bulleted_section(md, "## Concerns")
