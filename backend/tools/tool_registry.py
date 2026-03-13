from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from backend.services.scanner_service import build_markdown_report, scan_directory
from backend.tools.file_tools import write_text


class ToolError(RuntimeError):
    pass


WRITE_ALLOWED_PREFIXES = ("repos/", "runs/")


@dataclass
class ToolContext:
    workspace_root: Path
    db: Any = field(default=None)
    run_id: Optional[str] = field(default=None)
    task_id: Optional[str] = field(default=None)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    fn: Callable[..., Any]


_REGISTRY: Dict[str, ToolSpec] = {}

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


def register_tool(name: str, description: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if name in _REGISTRY:
            raise ToolError(f"Tool already registered: {name}")
        _REGISTRY[name] = ToolSpec(name=name, description=description, fn=fn)
        return fn
    return _decorator


def list_tools() -> Dict[str, str]:
    return {name: spec.description for name, spec in _REGISTRY.items()}


def _ensure_within_workspace(ctx: ToolContext, path: Path) -> Path:
    root = ctx.workspace_root.resolve()
    resolved = path.resolve()
    if resolved == root or root in resolved.parents:
        return resolved
    raise ToolError(f"Path escapes workspace: {path}")


def _resolve_target_dir(ctx: ToolContext, relative_dir: str = "") -> Path:
    if not relative_dir:
        return ctx.workspace_root.resolve()
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_dir)
    if not target.exists():
        raise ToolError(f"Target directory does not exist: {relative_dir}")
    if not target.is_dir():
        raise ToolError(f"Target is not a directory: {relative_dir}")
    return target


def _extract_repo_name(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    path = parsed.path.rstrip("/")
    if not path:
        raise ToolError(f"Invalid repository URL: {repo_url}")
    repo_name = path.split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    if not repo_name:
        raise ToolError(f"Could not extract repository name from URL: {repo_url}")
    if any(sep in repo_name for sep in ("/", "\\", "..")):
        raise ToolError(f"Unsafe repository name extracted from URL: {repo_url}")
    return repo_name


def _is_in_ignored_dir(base_dir: Path, path: Path) -> bool:
    relative_parts = path.relative_to(base_dir).parts
    return any(part in IGNORED_DIR_NAMES for part in relative_parts)


def _normalize_relative(ctx: ToolContext, raw_path: str) -> str:
    """
    Always return a clean relative path (no leading slash, no /app/workspace prefix).
    Handles both:
      - already relative: "runs/abc/file.json"
      - absolute inside container: "/app/workspace/runs/abc/file.json"
    """
    normalized = raw_path.replace("\\", "/")
    workspace_str = str(ctx.workspace_root).replace("\\", "/").rstrip("/")
    if normalized.startswith(workspace_str + "/"):
        normalized = normalized[len(workspace_str) + 1:]
    elif normalized.startswith("/app/workspace/"):
        normalized = normalized[len("/app/workspace/"):]
    return normalized.lstrip("/")


def _assert_write_allowed(relative_path: str) -> None:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if not any(normalized.startswith(prefix) for prefix in WRITE_ALLOWED_PREFIXES):
        raise ToolError(f"Write blocked outside allowed paths: {relative_path}")


def run_tool(tool_name: str, ctx: ToolContext, **kwargs: Any) -> Any:
    spec = _REGISTRY.get(tool_name)
    if not spec:
        raise ToolError(f"Unknown tool: {tool_name}")
    return spec.fn(ctx, **kwargs)


@register_tool(
    name="scan_workspace_in_dir",
    description="Scan a target directory inside workspace.",
)
def tool_scan_workspace_in_dir(ctx: ToolContext, relative_dir: str = "") -> Any:
    target_dir = _resolve_target_dir(ctx, relative_dir)
    return scan_directory(target_dir)


@register_tool(
    name="build_scan_report_md",
    description="Build markdown scan report from ScanResult.",
)
def tool_build_scan_report_md(ctx: ToolContext, scan_result: Any) -> str:
    return build_markdown_report(scan_result)


@register_tool(
    name="write_workspace_file",
    description="Write a text file inside workspace.",
)
def tool_write_workspace_file(ctx: ToolContext, relative_path: str, content: str) -> None:
    relative_path = _normalize_relative(ctx, relative_path)
    _assert_write_allowed(relative_path)
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(target, content)


@register_tool(
    name="write_workspace_json",
    description="Write a JSON file inside workspace.",
)
def tool_write_workspace_json(ctx: ToolContext, relative_path: str, data: object) -> None:
    relative_path = _normalize_relative(ctx, relative_path)
    _assert_write_allowed(relative_path)
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@register_tool(
    name="list_workspace_files_in_dir",
    description="List files under a target directory inside workspace recursively.",
)
def tool_list_workspace_files_in_dir(ctx: ToolContext, relative_dir: str = "") -> List[str]:
    target_dir = _resolve_target_dir(ctx, relative_dir)
    files: List[str] = []
    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue
        if _is_in_ignored_dir(target_dir, path):
            continue
        files.append(str(path.relative_to(ctx.workspace_root)).replace("\\", "/"))
    return sorted(files)


@register_tool(
    name="get_workspace_file_metadata",
    description="Return file metadata for files inside a target directory in workspace.",
)
def tool_get_workspace_file_metadata(ctx: ToolContext, relative_dir: str = "") -> List[Dict[str, Any]]:
    target_dir = _resolve_target_dir(ctx, relative_dir)
    items: List[Dict[str, Any]] = []
    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue
        if _is_in_ignored_dir(target_dir, path):
            continue
        rel_path = str(path.relative_to(ctx.workspace_root)).replace("\\", "/")
        suffix = path.suffix.lower()
        size = path.stat().st_size
        items.append({
            "path": rel_path,
            "name": path.name,
            "suffix": suffix,
            "size": size,
        })
    items.sort(key=lambda x: x["path"])
    return items


@register_tool(
    name="read_workspace_file",
    description="Read a text file inside workspace.",
)
def tool_read_workspace_file(ctx: ToolContext, relative_path: str) -> str:
    relative_path = _normalize_relative(ctx, relative_path)
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_path)
    if not target.exists():
        raise ToolError(f"Workspace file does not exist: {relative_path}")
    if not target.is_file():
        raise ToolError(f"Workspace path is not a file: {relative_path}")
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise ToolError(f"Failed to read workspace file: {relative_path} | error={e}") from e


@register_tool(
    name="search_workspace_text",
    description="Search for a text pattern in workspace files or a target directory.",
)
def tool_search_workspace_text(
    ctx: ToolContext, pattern: str, relative_dir: str = ""
) -> List[Dict[str, Any]]:
    target_dir = _resolve_target_dir(ctx, relative_dir)
    results: List[Dict[str, Any]] = []
    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue
        if _is_in_ignored_dir(target_dir, path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.lower() in line.lower():
                results.append({
                    "path": str(path.relative_to(ctx.workspace_root)).replace("\\", "/"),
                    "line": line_no,
                    "text": line.strip(),
                })
    return results


@register_tool(
    name="clone_git_repo",
    description="Clone a git repository into workspace/repos.",
)
def tool_clone_git_repo(ctx: ToolContext, repo_url: str) -> str:
    repo_url = (repo_url or "").strip()
    if not repo_url:
        raise ToolError("repo_url is required")

    repos_dir = _ensure_within_workspace(ctx, ctx.workspace_root / "repos")
    repos_dir.mkdir(parents=True, exist_ok=True)

    repo_name = _extract_repo_name(repo_url)
    target_dir = _ensure_within_workspace(ctx, repos_dir / repo_name)

    if target_dir.exists():
        if not target_dir.is_dir():
            raise ToolError(f"Clone target exists and is not a directory: {target_dir}")
        return str(target_dir.relative_to(ctx.workspace_root)).replace("\\", "/")

    completed = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
        check=False,
        capture_output=True,
        text=True,
    )

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        details = stderr or stdout or "unknown git error"
        if target_dir.exists() and not any(target_dir.iterdir()):
            try:
                target_dir.rmdir()
            except OSError:
                pass
        raise ToolError(f"git clone failed for {repo_url}: {details}")

    return str(target_dir.relative_to(ctx.workspace_root)).replace("\\", "/")

@register_tool(
    name="run_tests",
    description="Detect and run the test suite in a target directory. Returns pass/fail and output.",
)
def tool_run_tests(
    ctx: ToolContext,
    relative_dir: str = "",
    command: str | None = None,
) -> Dict[str, Any]:
    import subprocess

    target_dir = ctx.workspace_root / relative_dir if relative_dir else ctx.workspace_root
    target_dir = target_dir.resolve()

    if not target_dir.exists():
        return {
            "passed":  False,
            "output":  f"Target directory does not exist: {relative_dir}",
            "command": "",
        }

    # Auto-detect test runner if no command provided
    if not command:
        if (target_dir / "pytest.ini").exists() or \
           (target_dir / "setup.cfg").exists() or \
           (target_dir / "pyproject.toml").exists() or \
           any(target_dir.rglob("test_*.py")) or \
           any(target_dir.rglob("*_test.py")):
            command = "python -m pytest --tb=short -q"
        elif (target_dir / "package.json").exists():
            command = "npm test --watchAll=false --passWithNoTests"
        elif (target_dir / "go.mod").exists():
            command = "go test ./..."
        elif (target_dir / "Cargo.toml").exists():
            command = "cargo test"
        elif (target_dir / "pom.xml").exists():
            command = "mvn test -q"
        else:
            # No test suite detected
            return {
                "passed":  True,
                "output":  "No test suite detected in repository — skipping test execution.",
                "command": "",
            }

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output  = (result.stdout or "") + (result.stderr or "")
        passed  = result.returncode == 0
        return {
            "passed":  passed,
            "output":  output[:5000],  # cap to avoid giant payloads
            "command": command,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed":  False,
            "output":  f"Test run timed out after 120s (command: {command})",
            "command": command,
        }
    except Exception as e:
        return {
            "passed":  False,
            "output":  f"Test runner error: {e}",
            "command": command,
        }

@register_tool(
    name="write_code_file",
    description="Write a source code file inside workspace repos or runs directory.",
)
def tool_write_code_file(ctx: ToolContext, relative_path: str, content: str) -> None:
    relative_path = _normalize_relative(ctx, relative_path)
    _assert_write_allowed(relative_path)
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(target, content)

@register_tool(
    name="git_diff",
    description="Run git diff in a repo directory and return the output string.",
)
def tool_git_diff(ctx: ToolContext, relative_dir: str = "") -> str:
    target_dir = ctx.workspace_root / relative_dir if relative_dir else ctx.workspace_root
    target_dir = target_dir.resolve()

    if not target_dir.exists():
        return "(directory does not exist)"

    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        return output if output else "(no changes detected by git diff)"
    except Exception as e:
        return f"(git diff error: {e})"


@register_tool(
    name="git_commit",
    description="Stage all changes and create a git commit in a repo directory.",
)
def tool_git_commit(ctx: ToolContext, relative_dir: str = "", message: str = "AI fix") -> str:
    target_dir = ctx.workspace_root / relative_dir if relative_dir else ctx.workspace_root
    target_dir = target_dir.resolve()

    if not target_dir.exists():
        return "(directory does not exist)"

    try:
        subprocess.run(["git", "config", "user.email", "ai@dev-team.local"],
                       cwd=str(target_dir), capture_output=True)
        subprocess.run(["git", "config", "user.name",  "AI Dev Team"],
                       cwd=str(target_dir), capture_output=True)
        subprocess.run(["git", "add", "-A"],
                       cwd=str(target_dir), capture_output=True, timeout=30)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"(git commit error: {e})"

