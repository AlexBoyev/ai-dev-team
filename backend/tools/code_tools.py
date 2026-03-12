from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List

from backend.tools.tool_registry import ToolContext, ToolError, _ensure_within_workspace, register_tool

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pack",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".class",
    ".db", ".sqlite", ".sqlite3",
}


def _resolve_repo_path(ctx: ToolContext, relative_dir: str) -> Path:
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_dir)
    if not target.exists():
        raise ToolError(f"Repo path does not exist: {relative_dir}")
    if not target.is_dir():
        raise ToolError(f"Repo path is not a directory: {relative_dir}")
    return target


@register_tool(
    name="write_code_file",
    description="Write or overwrite a code file inside workspace/repos/.",
)
def tool_write_code_file(ctx: ToolContext, relative_path: str, content: str) -> str:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    if not normalized.startswith("repos/"):
        raise ToolError(f"write_code_file only allowed inside repos/: {relative_path}")
    target = _ensure_within_workspace(ctx, ctx.workspace_root / normalized)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", errors="replace")
    return f"Written: {normalized}"


@register_tool(
    name="read_code_file",
    description="Read a code file inside workspace/repos/.",
)
def tool_read_code_file(ctx: ToolContext, relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    target = _ensure_within_workspace(ctx, ctx.workspace_root / normalized)
    if not target.exists():
        raise ToolError(f"File does not exist: {normalized}")
    if target.suffix.lower() in BINARY_EXTENSIONS:
        raise ToolError(f"Binary file skipped: {normalized}")
    return target.read_text(encoding="utf-8", errors="replace")


@register_tool(
    name="git_create_branch",
    description="Create a new git branch inside a workspace repo.",
)
def tool_git_create_branch(ctx: ToolContext, relative_dir: str, branch_name: str) -> str:
    repo_path = _resolve_repo_path(ctx, relative_dir)
    result = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Branch may already exist — try switching to it
        switch = subprocess.run(
            ["git", "checkout", branch_name],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        if switch.returncode != 0:
            raise ToolError(f"git checkout -b failed: {stderr}")
    return f"On branch: {branch_name}"


@register_tool(
    name="git_diff",
    description="Return git diff for all staged/unstaged changes in a workspace repo.",
)
def tool_git_diff(ctx: ToolContext, relative_dir: str) -> str:
    repo_path = _resolve_repo_path(ctx, relative_dir)
    # Stage all changes first so diff is complete
    subprocess.run(["git", "add", "-A"], cwd=str(repo_path), capture_output=True)
    result = subprocess.run(
        ["git", "diff", "--staged"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ToolError(f"git diff failed: {result.stderr.strip()}")
    return result.stdout or "(no changes)"


@register_tool(
    name="git_commit",
    description="Commit all staged changes inside a workspace repo.",
)
def tool_git_commit(ctx: ToolContext, relative_dir: str, message: str) -> str:
    repo_path = _resolve_repo_path(ctx, relative_dir)

    subprocess.run(
        ["git", "config", "user.email", "agent@ai-dev-team.local"],
        cwd=str(repo_path), capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "AI Dev Team"],
        cwd=str(repo_path), capture_output=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=str(repo_path), capture_output=True)

    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "nothing to commit" in stderr or "nothing to commit" in result.stdout:
            return "Nothing to commit — working tree clean"
        raise ToolError(f"git commit failed: {stderr}")
    return result.stdout.strip().splitlines()[0] if result.stdout else "Committed"


@register_tool(
    name="run_tests",
    description="Run tests inside a workspace repo. Returns stdout+stderr output.",
)
def tool_run_tests(
    ctx: ToolContext,
    relative_dir: str,
    command: List[str] | None = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    repo_path = _resolve_repo_path(ctx, relative_dir)

    # Auto-detect test command if not provided
    if not command:
        if (repo_path / "pytest.ini").exists() or (repo_path / "pyproject.toml").exists():
            command = ["python", "-m", "pytest", "--tb=short", "-q"]
        elif (repo_path / "package.json").exists():
            command = ["npm", "test", "--", "--watchAll=false"]
        else:
            command = ["python", "-m", "pytest", "--tb=short", "-q"]

    try:
        result = subprocess.run(
            command,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")
        passed = result.returncode == 0
    except subprocess.TimeoutExpired:
        output = f"Tests timed out after {timeout}s"
        passed = False
    except FileNotFoundError as e:
        output = f"Test command not found: {e}"
        passed = False

    return {
        "passed": passed,
        "output": output[:8000],  # cap to avoid huge DB rows
        "returncode": result.returncode if "result" in dir() else -1,
        "command": " ".join(command),
    }
