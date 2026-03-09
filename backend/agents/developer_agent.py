from __future__ import annotations

from typing import Any, Dict

from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class DeveloperAgent(BaseAgent):
    """
    Milestone behavior (deterministic):
    - scan workspace
    - build base markdown report
    """

    def __init__(self, agent_id: str = "dev_1") -> None:
        super().__init__(AgentProfile(agent_id=agent_id, display_name="Developer", role="Developer"))

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        if task_name == "scan":
            scan_result = self._tool(ctx, "scan_workspace")
            return {"scan_result": scan_result}

        if task_name == "build_report":
            scan_result = payload["scan_result"]
            report_md = self._tool(ctx, "build_scan_report_md", scan_result=scan_result)
            return {"report_md": report_md}

        raise ValueError(f"DeveloperAgent: unknown task_name={task_name}")