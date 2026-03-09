from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from backend.services.scanner_service import scan_directory, build_markdown_report
from backend.services.insights_service import analyze_workspace, append_insights_to_report
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
    return {k: v.description for k, v in _REGISTRY.items()}


def _ensure_within_workspace(ctx: ToolContext, path: Path) -> Path:
    root = ctx.workspace_root.resolve()
    resolved = path.resolve()

    # Allow writing inside workspace only
    if resolved == root or root in resolved.parents:
        return resolved

    raise ToolError(f"Path escapes workspace: {path}")


def run_tool(tool_name: str, ctx: ToolContext, **kwargs: Any) -> Any:
    spec = _REGISTRY.get(tool_name)
    if not spec:
        raise ToolError(f"Unknown tool: {tool_name}")
    return spec.fn(ctx, **kwargs)


# -----------------------
# Wrapped existing logic
# -----------------------

@register_tool(
    name="scan_workspace",
    description="Scan workspace folder (counts, top folders, python samples).",
)
def tool_scan_workspace(ctx: ToolContext) -> Any:
    return scan_directory(ctx.workspace_root)


@register_tool(
    name="build_scan_report_md",
    description="Build markdown scan report from ScanResult.",
)
def tool_build_scan_report_md(ctx: ToolContext, scan_result: Any) -> str:
    # scan_result is scanner_service.ScanResult
    return build_markdown_report(scan_result)


@register_tool(
    name="analyze_workspace_insights",
    description="Analyze workspace for TODO/FIXME/HACK, suspicious strings, and largest files.",
)
def tool_analyze_workspace_insights(ctx: ToolContext) -> Any:
    return analyze_workspace(ctx.workspace_root)


@register_tool(
    name="append_insights_to_report_md",
    description="Append insights section to an existing markdown report.",
)
def tool_append_insights_to_report_md(ctx: ToolContext, report_md: str, insights: Any) -> str:
    # insights is insights_service.InsightsResult
    return append_insights_to_report(report_md, insights)


@register_tool(
    name="write_workspace_file",
    description="Write a text file inside workspace (safe sandboxed write).",
)
def tool_write_workspace_file(ctx: ToolContext, relative_path: str, content: str) -> None:
    target = _ensure_within_workspace(ctx, ctx.workspace_root / relative_path)
    write_text(target, content)