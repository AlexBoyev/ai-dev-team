from __future__ import annotations

from typing import List

from backend.core.tasks import PlannedTask


class ManagerAgent:
    def __init__(self, agent_id: str = "manager") -> None:
        self.agent_id = agent_id

    def build_plan(self) -> List[PlannedTask]:
        return [
            PlannedTask(
                title="Analyze workspace for TODO/FIXME + suspicious strings + large files",
                task_type="scan_and_report",
                assigned_agent="dev_1",
            ),
            PlannedTask(
                title="Generate insights summary",
                task_type="insights",
                assigned_agent="qa_1",
            ),
            PlannedTask(
                title="Write report to workspace",
                task_type="write_report",
                assigned_agent="devops",
                payload={"report_key": "report_md"},
            ),
        ]