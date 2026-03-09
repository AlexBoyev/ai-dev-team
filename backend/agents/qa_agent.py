from __future__ import annotations

from typing import Any, Dict, List

from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class QaAgent(BaseAgent):
    LARGE_FILE_WARNING_BYTES = 100_000
    VERY_LARGE_FILE_WARNING_BYTES = 300_000

    def __init__(self, agent_id: str = "qa_1") -> None:
        super().__init__(
            AgentProfile(
                agent_id=agent_id,
                display_name="Tester",
                role="Tester",
            )
        )

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        if task_name != "build_qa_findings":
            raise ValueError(f"QaAgent: unknown task_name={task_name}")

        target_subdir = str(payload.get("target_subdir", "")).strip()
        workspace_files = payload.get("workspace_files", []) or []
        workspace_metadata = payload.get("workspace_metadata", []) or []
        selected_files = payload.get("selected_files", []) or []
        report_md = str(payload.get("report_md", ""))

        findings = self._build_findings(
            ctx=ctx,
            target_subdir=target_subdir,
            workspace_files=workspace_files,
            workspace_metadata=workspace_metadata,
            selected_files=selected_files,
            report_md=report_md,
        )

        qa_findings_md = self._render_markdown(
            target_subdir=target_subdir,
            findings=findings,
        )

        return {
            "qa_findings": findings,
            "qa_findings_md": qa_findings_md,
            "result_message": "QA findings generated",
        }

    def _build_findings(
        self,
        ctx: ToolContext,
        target_subdir: str,
        workspace_files: List[str],
        workspace_metadata: List[Dict[str, Any]],
        selected_files: List[str],
        report_md: str,
    ) -> Dict[str, Any]:
        normalized_files = [str(path).replace("\\", "/") for path in workspace_files]
        file_set = set(normalized_files)

        inventory = self._analyze_inventory(normalized_files, workspace_metadata, selected_files)
        structure = self._analyze_structure(file_set)
        todo_findings = self._analyze_text_markers(ctx, target_subdir)
        large_files = self._find_large_files(workspace_metadata)
        risk_flags = self._build_risk_flags(
            inventory=inventory,
            structure=structure,
            todo_findings=todo_findings,
            large_files=large_files,
            report_md=report_md,
        )
        strengths = self._build_strengths(file_set, selected_files, todo_findings)

        return {
            "inventory": inventory,
            "structure": structure,
            "todo_findings": todo_findings,
            "large_files": large_files,
            "risk_flags": risk_flags,
            "strengths": strengths,
        }

    def _analyze_inventory(
        self,
        workspace_files: List[str],
        workspace_metadata: List[Dict[str, Any]],
        selected_files: List[str],
    ) -> Dict[str, Any]:
        total_files = len(workspace_files)
        total_selected = len(selected_files)

        ext_counts: Dict[str, int] = {}
        total_bytes = 0

        for item in workspace_metadata:
            ext = str(item.get("suffix", "")).lower()
            size = int(item.get("size", 0))
            total_bytes += size
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        ranked_ext = sorted(
            [(ext or "[no extension]", count) for ext, count in ext_counts.items()],
            key=lambda x: (-x[1], x[0]),
        )

        return {
            "total_files": total_files,
            "selected_files": total_selected,
            "total_bytes": total_bytes,
            "top_extensions": ranked_ext[:10],
        }

    def _analyze_structure(self, file_set: set[str]) -> Dict[str, Any]:
        def has_suffix(name: str) -> bool:
            return any(path.endswith(name) for path in file_set)

        def has_segment(segment: str) -> bool:
            token = f"/{segment.strip('/')}/"
            return any(token in f"/{path}/" for path in file_set)

        has_readme = any(path.lower().endswith("readme.md") or path.lower() == "readme.md" for path in file_set)
        has_tests = has_segment("tests") or has_segment("test")
        has_docker = has_suffix("Dockerfile") or has_suffix("docker-compose.yml") or has_suffix("docker-compose.yaml")
        has_python = any(path.endswith(".py") for path in file_set)
        has_node = has_suffix("package.json")
        has_java = has_suffix("pom.xml") or has_suffix("build.gradle") or has_suffix("build.gradle.kts")
        has_go = has_suffix("go.mod")
        has_rust = has_suffix("Cargo.toml")

        entrypoints = []
        for candidate in (
            "main.py",
            "app.py",
            "manage.py",
            "server.py",
            "index.html",
            "main.js",
            "main.ts",
            "src/main.ts",
            "src/main.tsx",
        ):
            if has_suffix(candidate):
                entrypoints.append(candidate)

        return {
            "has_readme": has_readme,
            "has_tests": has_tests,
            "has_docker": has_docker,
            "has_python": has_python,
            "has_node": has_node,
            "has_java": has_java,
            "has_go": has_go,
            "has_rust": has_rust,
            "entrypoints": entrypoints,
        }

    def _analyze_text_markers(self, ctx: ToolContext, target_subdir: str) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "todo": self._tool(ctx, "search_workspace_text", pattern="TODO", relative_dir=target_subdir),
            "fixme": self._tool(ctx, "search_workspace_text", pattern="FIXME", relative_dir=target_subdir),
            "hack": self._tool(ctx, "search_workspace_text", pattern="HACK", relative_dir=target_subdir),
        }

    def _find_large_files(self, workspace_metadata: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for item in workspace_metadata:
            path = str(item.get("path", ""))
            size = int(item.get("size", 0))

            if size >= self.LARGE_FILE_WARNING_BYTES:
                severity = "medium"
                if size >= self.VERY_LARGE_FILE_WARNING_BYTES:
                    severity = "high"

                results.append(
                    {
                        "path": path,
                        "size": size,
                        "severity": severity,
                    }
                )

        results.sort(key=lambda x: (-x["size"], x["path"]))
        return results[:15]

    def _build_risk_flags(
        self,
        inventory: Dict[str, Any],
        structure: Dict[str, Any],
        todo_findings: Dict[str, List[Dict[str, Any]]],
        large_files: List[Dict[str, Any]],
        report_md: str,
    ) -> List[Dict[str, str]]:
        risks: List[Dict[str, str]] = []

        if not structure["has_readme"]:
            risks.append(
                {
                    "severity": "medium",
                    "title": "Missing README",
                    "detail": "Repository does not appear to contain a README, which makes onboarding and run discovery harder.",
                }
            )

        if not structure["entrypoints"]:
            risks.append(
                {
                    "severity": "medium",
                    "title": "No clear entrypoint detected",
                    "detail": "The analyzer could not identify an obvious application entrypoint.",
                }
            )

        if not structure["has_tests"]:
            risks.append(
                {
                    "severity": "medium",
                    "title": "No test directory detected",
                    "detail": "No obvious test folder was found. Validation and safe refactoring may be harder.",
                }
            )

        if structure["has_python"] and not any(
            token in report_md for token in ("requirements.txt", "pyproject.toml", "setup.py")
        ):
            risks.append(
                {
                    "severity": "medium",
                    "title": "Python project without clear dependency manifest",
                    "detail": "Python files were found, but no obvious dependency file was highlighted in the report.",
                }
            )

        total_markers = (
            len(todo_findings["todo"])
            + len(todo_findings["fixme"])
            + len(todo_findings["hack"])
        )
        if total_markers > 0:
            risks.append(
                {
                    "severity": "medium" if total_markers < 10 else "high",
                    "title": "Deferred work markers found",
                    "detail": (
                        f"Found {len(todo_findings['todo'])} TODO, "
                        f"{len(todo_findings['fixme'])} FIXME, "
                        f"{len(todo_findings['hack'])} HACK markers."
                    ),
                }
            )

        if large_files:
            biggest = large_files[0]
            risks.append(
                {
                    "severity": biggest["severity"],
                    "title": "Large source/config files detected",
                    "detail": (
                        f"Largest flagged file is `{biggest['path']}` "
                        f"with size {biggest['size']} bytes."
                    ),
                }
            )

        if inventory["total_files"] > 1000:
            risks.append(
                {
                    "severity": "medium",
                    "title": "Repository may require selective analysis",
                    "detail": f"Filtered candidate file count is {inventory['total_files']}, which may require tighter ranking in future runs.",
                }
            )

        return risks

    def _build_strengths(
        self,
        file_set: set[str],
        selected_files: List[str],
        todo_findings: Dict[str, List[Dict[str, Any]]],
    ) -> List[str]:
        strengths: List[str] = []

        if any(path.lower().endswith("readme.md") or path.lower() == "readme.md" for path in file_set):
            strengths.append("README detected for high-level project orientation.")

        if selected_files:
            strengths.append(f"Key-file selection produced {len(selected_files)} prioritized files for analysis.")

        total_markers = (
            len(todo_findings["todo"])
            + len(todo_findings["fixme"])
            + len(todo_findings["hack"])
        )
        if total_markers == 0:
            strengths.append("No TODO/FIXME/HACK markers were found in scanned text files.")

        if any(path.endswith("Dockerfile") for path in file_set):
            strengths.append("Docker support appears to exist.")

        if any(path.endswith("package.json") for path in file_set) or any(path.endswith("requirements.txt") for path in file_set):
            strengths.append("Dependency manifest detected, which helps reproducibility.")

        return strengths

    def _render_markdown(self, target_subdir: str, findings: Dict[str, Any]) -> str:
        inventory = findings["inventory"]
        structure = findings["structure"]
        todo_findings = findings["todo_findings"]
        large_files = findings["large_files"]
        risk_flags = findings["risk_flags"]
        strengths = findings["strengths"]

        lines = [
            "# QA Findings",
            "",
            f"Target subdir: `{target_subdir or '.'}`",
            "",
            "## Inventory summary",
            "",
            f"- Candidate files scanned: {inventory['total_files']}",
            f"- Selected key files: {inventory['selected_files']}",
            f"- Total candidate size: {inventory['total_bytes']} bytes",
            "",
            "### Top file extensions",
            "",
        ]

        if inventory["top_extensions"]:
            for ext, count in inventory["top_extensions"]:
                lines.append(f"- `{ext}`: {count}")
        else:
            lines.append("- No file extensions recorded.")

        lines.extend(
            [
                "",
                "## Structure checks",
                "",
                f"- README present: {'Yes' if structure['has_readme'] else 'No'}",
                f"- Tests detected: {'Yes' if structure['has_tests'] else 'No'}",
                f"- Docker support detected: {'Yes' if structure['has_docker'] else 'No'}",
                f"- Entrypoint candidates detected: {', '.join(structure['entrypoints']) if structure['entrypoints'] else 'None'}",
                "",
                "## Deferred work markers",
                "",
                f"- TODO count: {len(todo_findings['todo'])}",
                f"- FIXME count: {len(todo_findings['fixme'])}",
                f"- HACK count: {len(todo_findings['hack'])}",
                "",
            ]
        )

        marker_sections = [
            ("TODO hits", todo_findings["todo"]),
            ("FIXME hits", todo_findings["fixme"]),
            ("HACK hits", todo_findings["hack"]),
        ]

        for title, items in marker_sections:
            lines.extend([f"### {title}", ""])
            if items:
                for item in items[:10]:
                    lines.append(
                        f"- `{item['path']}` line {item['line']}: {item['text']}"
                    )
            else:
                lines.append("- None found.")
            lines.append("")

        lines.extend(
            [
                "## Large files",
                "",
            ]
        )

        if large_files:
            for item in large_files:
                lines.append(
                    f"- `{item['path']}`: {item['size']} bytes ({item['severity']})"
                )
        else:
            lines.append("- No large text/code files exceeded the warning threshold.")

        lines.extend(
            [
                "",
                "## Risks",
                "",
            ]
        )

        if risk_flags:
            for risk in risk_flags:
                lines.append(
                    f"- **{risk['severity'].upper()}** — {risk['title']}: {risk['detail']}"
                )
        else:
            lines.append("- No major structural risks detected by rule-based QA checks.")

        lines.extend(
            [
                "",
                "## Strengths",
                "",
            ]
        )

        if strengths:
            for item in strengths:
                lines.append(f"- {item}")
        else:
            lines.append("- No notable strengths recorded.")

        return "\n".join(lines)