from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List
import subprocess
from backend.services.scanner_service import build_markdown_report, scan_directory
from backend.tools.file_tools import write_text


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolContext:
    workspace_root: Path


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    fn: Callable[..., Any]


_REGISTRY: Dict[str, ToolSpec] = {}


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
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(target, content)


@register_tool(
    name="write_workspace_json",
    description="Write a JSON file inside workspace.",
)
def tool_write_workspace_json(ctx: ToolContext, relative_path: str, data: object) -> None:
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
        if path.is_file():
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

        rel_path = str(path.relative_to(ctx.workspace_root)).replace("\\", "/")
        suffix = path.suffix.lower()
        size = path.stat().st_size

        items.append(
            {
                "path": rel_path,
                "name": path.name,
                "suffix": suffix,
                "size": size,
            }
        )

    items.sort(key=lambda x: x["path"])
    return items


@register_tool(
    name="read_workspace_file",
    description="Read a text file inside workspace.",
)
def tool_read_workspace_file(ctx: ToolContext, relative_path: str) -> str:
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_path)
    return target.read_text(encoding="utf-8")


@register_tool(
    name="search_workspace_text",
    description="Search for a text pattern in workspace files or a target directory.",
)
def tool_search_workspace_text(ctx: ToolContext, pattern: str, relative_dir: str = "") -> List[Dict[str, Any]]:
    target_dir = _resolve_target_dir(ctx, relative_dir)
    results: List[Dict[str, Any]] = []

    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            if pattern.lower() in line.lower():
                results.append(
                    {
                        "path": str(path.relative_to(ctx.workspace_root)).replace("\\", "/"),
                        "line": line_no,
                        "text": line.strip(),
                    }
                )

    return results


@register_tool(
    name="clone_git_repo",
    description="Clone a git repository into workspace/repos.",
)
def tool_clone_git_repo(ctx: ToolContext, repo_url: str) -> str:
    repos_dir = ctx.workspace_root / "repos"
    repos_dir.mkdir(exist_ok=True)

    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    target_dir = repos_dir / repo_name

    if target_dir.exists():
        return str(target_dir)

    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
        check=True,
    )

    return str(target_dir.relative_to(ctx.workspace_root))