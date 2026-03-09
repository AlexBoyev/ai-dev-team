from __future__ import annotations

from typing import Any, Dict, List, Tuple

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
        ".fbx",
        ".obj",
        ".blend",
        ".asset",
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
        "README",
        "main.py",
        "app.py",
        "manage.py",
        "index.html",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Makefile",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "go.mod",
        "Cargo.toml",
    }

    MAX_INDEXED_FILES = 2000
    MAX_SELECTED_FILES = 12
    MAX_FILE_SIZE_BYTES = 100_000
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

            truncated = False
            total_candidate_files = len(filtered_files)

            if len(filtered_files) > self.MAX_INDEXED_FILES:
                filtered_files = filtered_files[: self.MAX_INDEXED_FILES]
                allowed_paths = set(filtered_files)
                filtered_metadata = [
                    item for item in filtered_metadata
                    if str(item.get("path", "")) in allowed_paths
                ]
                truncated = True

            return {
                "workspace_files": filtered_files,
                "workspace_metadata": filtered_metadata,
                "inventory_stats": {
                    "target_subdir": target_subdir,
                    "total_candidate_files": total_candidate_files,
                    "indexed_files": len(filtered_files),
                    "truncated": truncated,
                    "max_indexed_files": self.MAX_INDEXED_FILES,
                },
                "target_subdir": target_subdir,
                "result_message": (
                    f"Indexed {len(filtered_files)} files"
                    + (" (truncated)" if truncated else "")
                ),
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
                            "reason": "Filtered out as ignored or non-source path",
                        }
                    )
                    continue

                try:
                    metadata_list = self._tool(
                        ctx,
                        "get_workspace_file_metadata",
                        relative_dir=target_subdir,
                    )
                    size_lookup = {
                        str(item.get("path", "")): int(item.get("size", 0))
                        for item in metadata_list
                    }
                    file_size = size_lookup.get(rel_path, 0)
                except Exception:
                    file_size = 0

                if file_size > self.MAX_FILE_SIZE_BYTES:
                    skipped_files.append(
                        {
                            "path": rel_path,
                            "reason": (
                                f"Skipped because file size {file_size} exceeds "
                                f"limit {self.MAX_FILE_SIZE_BYTES}"
                            ),
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
                        f", skipped {len(skipped_files)} files"
                        if skipped_files
                        else ""
                    )
                ),
            }

        if task_name == "scan_and_report":
            scan_result = self._tool(ctx, "scan_workspace_in_dir", relative_dir=target_subdir)
            base_report_md = self._tool(ctx, "build_scan_report_md", scan_result=scan_result)

            metadata = self._tool(ctx, "get_workspace_file_metadata", relative_dir=target_subdir)
            workspace_files = self._tool(ctx, "list_workspace_files_in_dir", relative_dir=target_subdir)

            candidate_metadata = [
                item for item in metadata
                if self._is_candidate_path(str(item.get("path", "")))
            ]
            candidate_files = [
                path for path in workspace_files
                if self._is_candidate_path(path)
            ]

            intelligence = self._build_repo_intelligence(
                target_subdir=target_subdir,
                workspace_files=candidate_files,
                workspace_metadata=candidate_metadata,
            )

            report_lines = [
                "# Repository Report",
                "",
                f"Target subdir: `{target_subdir or '.'}`",
                "",
                "## Project overview",
                "",
                f"- Project type: {intelligence['project_type']}",
                f"- Languages: {', '.join(intelligence['languages']) if intelligence['languages'] else 'Unknown'}",
                f"- Frameworks / tools: {', '.join(intelligence['frameworks']) if intelligence['frameworks'] else 'None detected'}",
                f"- Assets detected: {'Yes' if intelligence['assets_detected'] else 'No'}",
                "",
                "## How it likely runs",
                "",
            ]

            if intelligence["run_hints"]:
                for hint in intelligence["run_hints"]:
                    report_lines.append(f"- {hint}")
            else:
                report_lines.append("- No confident run command detected.")

            report_lines.extend(
                [
                    "",
                    "## Where to start reading",
                    "",
                ]
            )

            if intelligence["reading_order"]:
                for idx, path in enumerate(intelligence["reading_order"], start=1):
                    report_lines.append(f"{idx}. `{path}`")
            else:
                report_lines.append("1. No clear reading order detected.")

            report_lines.extend(
                [
                    "",
                    "## Important files",
                    "",
                ]
            )

            if intelligence["important_files"]:
                for path in intelligence["important_files"]:
                    report_lines.append(f"- `{path}`")
            else:
                report_lines.append("- No important files detected.")

            report_lines.extend(
                [
                    "",
                    "## Entrypoint candidates",
                    "",
                ]
            )

            if intelligence["entrypoints"]:
                for path in intelligence["entrypoints"]:
                    report_lines.append(f"- `{path}`")
            else:
                report_lines.append("- No clear entrypoint candidates detected.")

            report_lines.extend(
                [
                    "",
                    "## Repository limits and indexing",
                    "",
                    f"- Candidate files after filtering: {len(candidate_files)}",
                    f"- Indexed file limit: {self.MAX_INDEXED_FILES}",
                    f"- Selected file limit: {self.MAX_SELECTED_FILES}",
                    f"- Max file size for summarization: {self.MAX_FILE_SIZE_BYTES} bytes",
                    "",
                    "## Raw structure scan",
                    "",
                    base_report_md,
                ]
            )

            report_md = "\n".join(report_lines)

            return {
                "scan_result": scan_result,
                "repo_intelligence": intelligence,
                "report_md": report_md,
                "result_message": "Scan complete",
            }

        raise ValueError(f"DeveloperAgent: unknown task_name={task_name}")

    def _build_repo_intelligence(
        self,
        target_subdir: str,
        workspace_files: List[str],
        workspace_metadata: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        paths = set(workspace_files)

        languages = self._detect_languages(workspace_metadata)
        frameworks = self._detect_frameworks(paths)
        assets_detected = self._detect_assets(workspace_files)
        project_type = self._detect_project_type(paths, languages, frameworks, assets_detected)
        important_files = self._find_important_files(workspace_files)
        entrypoints = self._find_entrypoints(workspace_files)
        run_hints = self._build_run_hints(paths, frameworks, languages)
        reading_order = self._build_reading_order(
            workspace_files=workspace_files,
            important_files=important_files,
            entrypoints=entrypoints,
        )

        return {
            "target_subdir": target_subdir,
            "project_type": project_type,
            "languages": languages,
            "frameworks": frameworks,
            "assets_detected": assets_detected,
            "important_files": important_files,
            "entrypoints": entrypoints,
            "run_hints": run_hints,
            "reading_order": reading_order,
        }

    def _detect_languages(self, metadata: List[Dict[str, Any]]) -> List[str]:
        counts: Dict[str, int] = {}

        ext_to_lang = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".jsx": "JavaScript",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "CSS",
            ".java": "Java",
            ".kt": "Kotlin",
            ".kts": "Kotlin",
            ".go": "Go",
            ".rs": "Rust",
            ".c": "C",
            ".cpp": "C++",
            ".h": "C/C++ Header",
            ".hpp": "C++ Header",
            ".cs": "C#",
            ".php": "PHP",
            ".rb": "Ruby",
            ".json": "JSON",
            ".yml": "YAML",
            ".yaml": "YAML",
            ".toml": "TOML",
            ".xml": "XML",
            ".md": "Markdown",
        }

        for item in metadata:
            suffix = str(item.get("suffix", "")).lower()
            lang = ext_to_lang.get(suffix)
            if not lang:
                continue
            counts[lang] = counts.get(lang, 0) + 1

        ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        return [name for name, _ in ranked[:6]]

    def _detect_frameworks(self, paths: set[str]) -> List[str]:
        frameworks: List[str] = []

        def has(name: str) -> bool:
            return any(path.endswith(name) for path in paths)

        if has("requirements.txt") or has("pyproject.toml") or has("setup.py"):
            frameworks.append("Python project")

        if has("package.json"):
            frameworks.append("Node.js")

        if has("Dockerfile") or has("docker-compose.yml") or has("docker-compose.yaml"):
            frameworks.append("Docker")

        if has("pom.xml") or has("build.gradle") or has("build.gradle.kts"):
            frameworks.append("JVM build")

        if has("go.mod"):
            frameworks.append("Go modules")

        if has("Cargo.toml"):
            frameworks.append("Rust Cargo")

        if has("manage.py"):
            frameworks.append("Django")

        if has("main.py") and has("requirements.txt"):
            frameworks.append("Python app")

        if any(path.endswith("package.json") and "next" in path.lower() for path in paths):
            frameworks.append("Next.js")

        return frameworks

    def _detect_assets(self, workspace_files: List[str]) -> bool:
        asset_markers = (
            "/assets/",
            "/sprites/",
            "/images/",
            "/audio/",
            "/sounds/",
            "/textures/",
            "/models/",
        )

        for path in workspace_files:
            normalized = f"/{path.lower()}/"
            if any(marker in normalized for marker in asset_markers):
                return True

        return False

    def _detect_project_type(
        self,
        paths: set[str],
        languages: List[str],
        frameworks: List[str],
        assets_detected: bool,
    ) -> str:
        path_text = " ".join(sorted(paths)).lower()

        if assets_detected:
            if "python" in " ".join(languages).lower():
                return "Game or interactive project (likely Python-based)"
            return "Game or interactive project"

        if any(path.endswith("package.json") for path in paths) and any(
            path.endswith(("index.html", "vite.config.ts", "vite.config.js"))
            for path in paths
        ):
            return "Frontend web application"

        if "Python" in languages and any(path.endswith(("main.py", "app.py", "manage.py")) for path in paths):
            return "Python application"

        if any(path.endswith(("pom.xml", "build.gradle", "build.gradle.kts")) for path in paths):
            return "JVM application"

        if any(path.endswith("go.mod") for path in paths):
            return "Go application"

        if any(path.endswith("Cargo.toml") for path in paths):
            return "Rust application"

        if "library" in path_text:
            return "Library or reusable package"

        if len(paths) > 300:
            return "Large codebase or possible monorepo"

        return "General software repository"

    def _find_important_files(self, workspace_files: List[str]) -> List[str]:
        scored: List[Tuple[int, str]] = []

        for path in workspace_files:
            filename = path.split("/")[-1]
            score = 0

            if filename in self.PREFERRED_NAMES:
                score += 100

            if filename.lower().startswith("readme"):
                score += 120

            if path.endswith(("requirements.txt", "pyproject.toml", "package.json", "Dockerfile")):
                score += 80

            if path.endswith(("main.py", "app.py", "manage.py", "index.html")):
                score += 70

            if score > 0:
                scored.append((score, path))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [path for _, path in scored[:10]]

    def _find_entrypoints(self, workspace_files: List[str]) -> List[str]:
        candidates: List[Tuple[int, str]] = []

        for path in workspace_files:
            filename = path.split("/")[-1].lower()
            score = 0

            if filename in {"main.py", "app.py", "manage.py", "run.py"}:
                score += 100
            if filename in {"index.html", "server.py"}:
                score += 80
            if "/src/" in f"/{path}/":
                score += 10

            if score > 0:
                candidates.append((score, path))

        candidates.sort(key=lambda x: (-x[0], x[1]))
        return [path for _, path in candidates[:6]]

    def _build_run_hints(
        self,
        paths: set[str],
        frameworks: List[str],
        languages: List[str],
    ) -> List[str]:
        hints: List[str] = []

        def has(name: str) -> bool:
            return any(path.endswith(name) for path in paths)

        if has("requirements.txt") and has("main.py"):
            hints.append("Likely setup: `pip install -r requirements.txt`")
            hints.append("Likely run: `python main.py`")

        if has("pyproject.toml") and has("main.py"):
            hints.append("Likely run: project may use `python main.py` or a package entrypoint from `pyproject.toml`")

        if has("manage.py"):
            hints.append("Likely run: `python manage.py runserver`")

        if has("package.json"):
            hints.append("Likely setup: `npm install`")
            hints.append("Likely run: inspect `package.json` scripts such as `npm run dev` or `npm start`")

        if has("Dockerfile"):
            hints.append("Container support detected via `Dockerfile`")

        if has("docker-compose.yml") or has("docker-compose.yaml"):
            hints.append("Multi-service run may use `docker compose up`")

        if has("Makefile"):
            hints.append("Build/run shortcuts may be defined in `Makefile`")

        if has("pom.xml"):
            hints.append("Likely JVM build: `mvn test` / `mvn spring-boot:run` depending on project type")

        if has("build.gradle") or has("build.gradle.kts"):
            hints.append("Likely JVM build: use Gradle tasks such as `gradle build` or `gradle run`")

        if has("go.mod"):
            hints.append("Likely run: `go run .` or `go test ./...`")

        if has("Cargo.toml"):
            hints.append("Likely run: `cargo run` / `cargo test`")

        return hints[:8]

    def _build_reading_order(
        self,
        workspace_files: List[str],
        important_files: List[str],
        entrypoints: List[str],
    ) -> List[str]:
        ordered: List[str] = []

        def add(path: str) -> None:
            if path not in ordered:
                ordered.append(path)

        for path in important_files:
            add(path)

        for path in entrypoints:
            add(path)

        for path in workspace_files:
            lowered = path.lower()
            if lowered.endswith("/readme.md") or lowered == "readme.md":
                add(path)

        for path in workspace_files:
            if "/src/" in f"/{path}/":
                add(path)
                if len(ordered) >= 10:
                    break

        return ordered[:10]

    def _select_key_files(self, metadata: List[Dict[str, Any]]) -> List[str]:
        filtered: List[tuple[int, str]] = []

        for item in metadata:
            path = str(item.get("path", ""))
            if not self._is_candidate_path(path):
                continue

            size = int(item.get("size", 0))
            filename = path.split("/")[-1]
            ext = self._get_extension(filename)

            if size > self.MAX_FILE_SIZE_BYTES:
                continue

            score = 0

            if filename in self.PREFERRED_NAMES:
                score += 100

            if filename.lower().startswith("readme"):
                score += 120

            if ext in self.ALLOWED_EXTENSIONS:
                score += 30

            if path.endswith(("requirements.txt", "pyproject.toml", "package.json", "Dockerfile")):
                score += 70

            if path.endswith(("main.py", "app.py", "manage.py", "index.html")):
                score += 60

            if "/src/" in f"/{path}/":
                score += 20

            if "/backend/" in f"/{path}/" or "/frontend/" in f"/{path}/":
                score += 15

            if "/tests/" in f"/{path}/" or path.startswith("tests/"):
                score += 10

            if size > 0:
                score += min(size // 300, 20)

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