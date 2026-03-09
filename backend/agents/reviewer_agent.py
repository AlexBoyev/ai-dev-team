from __future__ import annotations

import re
from typing import Any, Dict, List

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

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        if task_name != "review_outputs":
            raise ValueError(f"ReviewerAgent: unknown task_name={task_name}")

        target_subdir = str(payload.get("target_subdir", "")).strip()
        report_md = str(payload.get("report_md", ""))
        code_summary_md = str(payload.get("code_summary_md", ""))
        qa_findings_md = str(payload.get("qa_findings_md", ""))

        review = self._build_review(
            target_subdir=target_subdir,
            report_md=report_md,
            code_summary_md=code_summary_md,
            qa_findings_md=qa_findings_md,
        )

        review_md = self._render_markdown(
            target_subdir=target_subdir,
            review=review,
        )

        return {
            "review": review,
            "review_md": review_md,
            "result_message": "Review complete",
        }

    def _build_review(
        self,
        target_subdir: str,
        report_md: str,
        code_summary_md: str,
        qa_findings_md: str,
    ) -> Dict[str, Any]:
        presence = self._check_presence(
            report_md=report_md,
            code_summary_md=code_summary_md,
            qa_findings_md=qa_findings_md,
        )

        consistency = self._check_consistency(
            expected_target_subdir=target_subdir,
            report_md=report_md,
            code_summary_md=code_summary_md,
            qa_findings_md=qa_findings_md,
        )

        coverage = self._check_coverage(
            report_md=report_md,
            code_summary_md=code_summary_md,
            qa_findings_md=qa_findings_md,
        )

        strengths = self._build_strengths(
            presence=presence,
            consistency=consistency,
            coverage=coverage,
        )

        concerns = self._build_concerns(
            presence=presence,
            consistency=consistency,
            coverage=coverage,
        )

        next_actions = self._build_next_actions(
            presence=presence,
            consistency=consistency,
            coverage=coverage,
        )

        overall_status = self._derive_status(
            presence=presence,
            consistency=consistency,
            coverage=coverage,
        )

        return {
            "overall_status": overall_status,
            "presence": presence,
            "consistency": consistency,
            "coverage": coverage,
            "strengths": strengths,
            "concerns": concerns,
            "next_actions": next_actions,
        }

    def _check_presence(
        self,
        report_md: str,
        code_summary_md: str,
        qa_findings_md: str,
    ) -> Dict[str, Any]:
        return {
            "report_present": bool(report_md.strip()),
            "code_summary_present": bool(code_summary_md.strip()),
            "qa_findings_present": bool(qa_findings_md.strip()),
            "report_length": len(report_md.strip()),
            "code_summary_length": len(code_summary_md.strip()),
            "qa_findings_length": len(qa_findings_md.strip()),
        }

    def _check_consistency(
        self,
        expected_target_subdir: str,
        report_md: str,
        code_summary_md: str,
        qa_findings_md: str,
    ) -> Dict[str, Any]:
        report_target = self._extract_target_subdir(report_md)
        code_target = self._extract_target_subdir(code_summary_md)
        qa_target = self._extract_target_subdir(qa_findings_md)

        target_matches = []
        expected = expected_target_subdir or "."

        for name, actual in (
            ("report_md", report_target),
            ("code_summary_md", code_target),
            ("qa_findings_md", qa_target),
        ):
            target_matches.append(
                {
                    "artifact": name,
                    "expected": expected,
                    "actual": actual or "[missing]",
                    "matches": (actual == expected),
                }
            )

        report_sections = self._extract_headings(report_md)
        code_sections = self._extract_headings(code_summary_md)
        qa_sections = self._extract_headings(qa_findings_md)

        return {
            "report_target_subdir": report_target,
            "code_target_subdir": code_target,
            "qa_target_subdir": qa_target,
            "target_matches": target_matches,
            "report_sections": report_sections,
            "code_sections": code_sections,
            "qa_sections": qa_sections,
        }

    def _check_coverage(
        self,
        report_md: str,
        code_summary_md: str,
        qa_findings_md: str,
    ) -> Dict[str, Any]:
        report_has_project_overview = "## Project overview" in report_md
        report_has_run_hints = "## How it likely runs" in report_md
        report_has_reading_order = "## Where to start reading" in report_md
        report_has_entrypoints = "## Entrypoint candidates" in report_md

        code_file_sections = self._count_h2_sections(code_summary_md)
        code_has_skipped_section = "## Skipped files" in code_summary_md

        qa_has_inventory = "## Inventory summary" in qa_findings_md
        qa_has_structure = "## Structure checks" in qa_findings_md
        qa_has_risks = "## Risks" in qa_findings_md
        qa_has_strengths = "## Strengths" in qa_findings_md

        qa_todo_count = self._extract_numeric_bullet(qa_findings_md, "TODO count")
        qa_fixme_count = self._extract_numeric_bullet(qa_findings_md, "FIXME count")
        qa_hack_count = self._extract_numeric_bullet(qa_findings_md, "HACK count")

        return {
            "report_has_project_overview": report_has_project_overview,
            "report_has_run_hints": report_has_run_hints,
            "report_has_reading_order": report_has_reading_order,
            "report_has_entrypoints": report_has_entrypoints,
            "code_file_sections": code_file_sections,
            "code_has_skipped_section": code_has_skipped_section,
            "qa_has_inventory": qa_has_inventory,
            "qa_has_structure": qa_has_structure,
            "qa_has_risks": qa_has_risks,
            "qa_has_strengths": qa_has_strengths,
            "qa_todo_count": qa_todo_count,
            "qa_fixme_count": qa_fixme_count,
            "qa_hack_count": qa_hack_count,
        }

    def _build_strengths(
        self,
        presence: Dict[str, Any],
        consistency: Dict[str, Any],
        coverage: Dict[str, Any],
    ) -> List[str]:
        strengths: List[str] = []

        if (
            presence["report_present"]
            and presence["code_summary_present"]
            and presence["qa_findings_present"]
        ):
            strengths.append("All major analysis artifacts were generated successfully.")

        if all(item["matches"] for item in consistency["target_matches"]):
            strengths.append("All artifacts reference the same target subdirectory consistently.")

        if coverage["report_has_project_overview"]:
            strengths.append("Repository report includes a high-level project overview.")

        if coverage["report_has_run_hints"]:
            strengths.append("Repository report includes likely run/setup hints.")

        if coverage["report_has_reading_order"]:
            strengths.append("Repository report provides a recommended reading order.")

        if coverage["code_file_sections"] >= 3:
            strengths.append(
                f"Code summary covers multiple prioritized files ({coverage['code_file_sections']} sections)."
            )

        if coverage["qa_has_risks"] and coverage["qa_has_strengths"]:
            strengths.append("QA findings include both risks and strengths, improving balance.")

        return strengths

    def _build_concerns(
        self,
        presence: Dict[str, Any],
        consistency: Dict[str, Any],
        coverage: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        concerns: List[Dict[str, str]] = []

        if not presence["report_present"]:
            concerns.append(
                {
                    "severity": "high",
                    "title": "Missing repository report",
                    "detail": "The main repository report artifact is empty or missing.",
                }
            )

        if not presence["code_summary_present"]:
            concerns.append(
                {
                    "severity": "high",
                    "title": "Missing code summary",
                    "detail": "The code summary artifact is empty or missing.",
                }
            )

        if not presence["qa_findings_present"]:
            concerns.append(
                {
                    "severity": "high",
                    "title": "Missing QA findings",
                    "detail": "The QA findings artifact is empty or missing.",
                }
            )

        mismatches = [item for item in consistency["target_matches"] if not item["matches"]]
        if mismatches:
            concerns.append(
                {
                    "severity": "high",
                    "title": "Artifact target mismatch",
                    "detail": "Not all generated artifacts reference the same target subdirectory.",
                }
            )

        if not coverage["report_has_project_overview"]:
            concerns.append(
                {
                    "severity": "medium",
                    "title": "Report lacks project overview",
                    "detail": "The repository report does not clearly identify what kind of project this is.",
                }
            )

        if not coverage["report_has_run_hints"]:
            concerns.append(
                {
                    "severity": "medium",
                    "title": "Report lacks run guidance",
                    "detail": "The repository report does not provide likely setup or run hints.",
                }
            )

        if not coverage["report_has_reading_order"]:
            concerns.append(
                {
                    "severity": "medium",
                    "title": "Report lacks reading path",
                    "detail": "The repository report does not guide the reader on where to start.",
                }
            )

        if coverage["code_file_sections"] == 0:
            concerns.append(
                {
                    "severity": "medium",
                    "title": "No summarized file sections",
                    "detail": "The code summary does not appear to contain per-file sections.",
                }
            )

        if not coverage["qa_has_inventory"] or not coverage["qa_has_structure"]:
            concerns.append(
                {
                    "severity": "medium",
                    "title": "QA findings are structurally incomplete",
                    "detail": "The QA report is missing inventory or structure checks.",
                }
            )

        total_markers = (
            coverage["qa_todo_count"]
            + coverage["qa_fixme_count"]
            + coverage["qa_hack_count"]
        )
        if total_markers >= 10:
            concerns.append(
                {
                    "severity": "medium",
                    "title": "High number of deferred-work markers",
                    "detail": f"QA findings report {total_markers} TODO/FIXME/HACK markers.",
                }
            )

        return concerns

    def _build_next_actions(
        self,
        presence: Dict[str, Any],
        consistency: Dict[str, Any],
        coverage: Dict[str, Any],
    ) -> List[str]:
        actions: List[str] = []

        if not all(item["matches"] for item in consistency["target_matches"]):
            actions.append("Fix payload propagation so all artifacts reference the same target subdirectory.")

        if not coverage["report_has_project_overview"]:
            actions.append("Improve repository intelligence detection for project type, stack, and framework hints.")

        if not coverage["report_has_run_hints"]:
            actions.append("Improve run/build/test hint detection from README and config files.")

        if not coverage["report_has_reading_order"]:
            actions.append("Strengthen prioritized reading-order generation for new users.")

        if coverage["code_file_sections"] < 3:
            actions.append("Improve key-file selection so the code summary covers more of the important code paths.")

        if not coverage["qa_has_risks"]:
            actions.append("Add more rule-based QA checks so the report highlights meaningful risks.")

        if not actions:
            actions.append("Next step: add repo-type-specific intelligence rules and larger-repo scaling limits.")

        return actions[:6]

    def _derive_status(
        self,
        presence: Dict[str, Any],
        consistency: Dict[str, Any],
        coverage: Dict[str, Any],
    ) -> str:
        if not (
            presence["report_present"]
            and presence["code_summary_present"]
            and presence["qa_findings_present"]
        ):
            return "needs_attention"

        if not all(item["matches"] for item in consistency["target_matches"]):
            return "needs_attention"

        if (
            coverage["report_has_project_overview"]
            and coverage["report_has_run_hints"]
            and coverage["report_has_reading_order"]
            and coverage["qa_has_risks"]
            and coverage["qa_has_strengths"]
            and coverage["code_file_sections"] >= 1
        ):
            return "good"

        return "acceptable"

    def _extract_target_subdir(self, md: str) -> str:
        match = re.search(r"Target subdir:\s*`([^`]+)`", md)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_headings(self, md: str) -> List[str]:
        headings: List[str] = []
        for line in md.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped)
        return headings

    def _count_h2_sections(self, md: str) -> int:
        count = 0
        for line in md.splitlines():
            if line.strip().startswith("## "):
                count += 1
        return count

    def _extract_numeric_bullet(self, md: str, label: str) -> int:
        pattern = rf"-\s*{re.escape(label)}:\s*(\d+)"
        match = re.search(pattern, md)
        if match:
            return int(match.group(1))
        return 0

    def _render_markdown(self, target_subdir: str, review: Dict[str, Any]) -> str:
        presence = review["presence"]
        consistency = review["consistency"]
        coverage = review["coverage"]
        strengths = review["strengths"]
        concerns = review["concerns"]
        next_actions = review["next_actions"]

        lines = [
            "# Review",
            "",
            f"Target subdir: `{target_subdir or '.'}`",
            "",
            "## Overall status",
            "",
            f"- Status: **{review['overall_status']}**",
            "",
            "## Artifact presence",
            "",
            f"- report.md present: {'Yes' if presence['report_present'] else 'No'}",
            f"- code_summary.md present: {'Yes' if presence['code_summary_present'] else 'No'}",
            f"- qa_findings.md present: {'Yes' if presence['qa_findings_present'] else 'No'}",
            f"- report.md length: {presence['report_length']}",
            f"- code_summary.md length: {presence['code_summary_length']}",
            f"- qa_findings.md length: {presence['qa_findings_length']}",
            "",
            "## Consistency checks",
            "",
        ]

        for item in consistency["target_matches"]:
            lines.append(
                f"- `{item['artifact']}` target = `{item['actual']}` "
                f"(expected `{item['expected']}`) -> {'OK' if item['matches'] else 'MISMATCH'}"
            )

        lines.extend(
            [
                "",
                "## Coverage checks",
                "",
                f"- Project overview present: {'Yes' if coverage['report_has_project_overview'] else 'No'}",
                f"- Run hints present: {'Yes' if coverage['report_has_run_hints'] else 'No'}",
                f"- Reading order present: {'Yes' if coverage['report_has_reading_order'] else 'No'}",
                f"- Entrypoint section present: {'Yes' if coverage['report_has_entrypoints'] else 'No'}",
                f"- Code summary sections: {coverage['code_file_sections']}",
                f"- Code summary skipped-files section present: {'Yes' if coverage['code_has_skipped_section'] else 'No'}",
                f"- QA inventory section present: {'Yes' if coverage['qa_has_inventory'] else 'No'}",
                f"- QA structure section present: {'Yes' if coverage['qa_has_structure'] else 'No'}",
                f"- QA risks section present: {'Yes' if coverage['qa_has_risks'] else 'No'}",
                f"- QA strengths section present: {'Yes' if coverage['qa_has_strengths'] else 'No'}",
                f"- TODO count reported: {coverage['qa_todo_count']}",
                f"- FIXME count reported: {coverage['qa_fixme_count']}",
                f"- HACK count reported: {coverage['qa_hack_count']}",
                "",
                "## Strengths",
                "",
            ]
        )

        if strengths:
            for item in strengths:
                lines.append(f"- {item}")
        else:
            lines.append("- No major strengths recorded.")

        lines.extend(
            [
                "",
                "## Concerns",
                "",
            ]
        )

        if concerns:
            for item in concerns:
                lines.append(
                    f"- **{item['severity'].upper()}** — {item['title']}: {item['detail']}"
                )
        else:
            lines.append("- No major concerns detected.")

        lines.extend(
            [
                "",
                "## Recommended next actions",
                "",
            ]
        )

        for idx, action in enumerate(next_actions, start=1):
            lines.append(f"{idx}. {action}")

        return "\n".join(lines)