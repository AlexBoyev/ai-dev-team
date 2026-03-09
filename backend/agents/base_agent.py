from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from backend.tools.tool_registry import ToolContext, run_tool


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    display_name: str
    role: str  # e.g. "Developer", "Tester", "DevOps"


class BaseAgent:
    def __init__(self, profile: AgentProfile) -> None:
        self.profile = profile

    def run_task(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Deterministic execution (no LLM). Returns a dict that orchestrator can store into TaskState.result.
        """
        payload = payload or {}
        return self._run(task_name=task_name, ctx=ctx, payload=payload)

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    # Convenience wrapper
    def _tool(self, ctx: ToolContext, tool_name: str, **kwargs: Any) -> Any:
        return run_tool(tool_name, ctx, **kwargs)