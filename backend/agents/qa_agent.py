from __future__ import annotations

from typing import Any, Dict

from backend.agents.base_agent import BaseAgent, AgentProfile
from backend.tools.tool_registry import ToolContext


class QaAgent(BaseAgent):
    """
    Milestone behavior (deterministic):
    - analyze insights
    - append to report
    """

    def __init__(self, agent_id: str = "qa_1") -> None:
        super().__init__(AgentProfile(agent_id=agent_id, display_name="Tester", role="Tester"))

    def _run(self, task_name: str, ctx: ToolContext, payload: Dict[str, Any]) -> Dict[str, Any]:
        if task_name == "insights":
            insights = self._tool(ctx, "analyze_workspace_insights")
            return {"insights": insights}

        if task_name == "append_insights":
            report_md = payload["report_md"]
            insights = payload["insights"]
            updated_md = self._tool(ctx, "append_insights_to_report_md", report_md=report_md, insights=insights)
            return {"report_md": updated_md}

        raise ValueError(f"QaAgent: unknown task_name={task_name}")