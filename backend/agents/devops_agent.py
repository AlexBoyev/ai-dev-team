from __future__ import annotations

from typing import Any, Dict

from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class DevOpsAgent(BaseAgent):
    """
    Milestone behavior (deterministic):
    - write report.md to workspace/
    """

    def __init__(self, agent_id: str = "devops") -> None:
        super().__init__(AgentProfile(agent_id=agent_id, display_name="DevOps", role="DevOps"))

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        if task_name == "write_report":
            report_md = payload["report_md"]
            self._tool(ctx, "write_workspace_file", relative_path="report.md", content=report_md)
            return {"written": "workspace/report.md"}

        raise ValueError(f"DevOpsAgent: unknown task_name={task_name}")