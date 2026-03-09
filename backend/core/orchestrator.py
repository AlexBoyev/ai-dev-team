from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict

from backend.agents import DeveloperAgent, DevOpsAgent, QaAgent, ReviewerAgent
from backend.agents.manager import ManagerAgent
from backend.core.memory import (
    TaskState,
    add_log,
    get_run_in_progress,
    set_run_in_progress,
    snapshot_for_api,
    update_agent,
    update_task,
    upsert_task,
)
from backend.core.persistence import new_run_id, snapshot_run
from backend.core.tasks import PlannedTask
from backend.tools.tool_registry import ToolContext

WORKSPACE_ROOT = Path("workspace")


def _ensure_workspace() -> Path:
    root = WORKSPACE_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _new_task(title: str, assigned_agent: str) -> TaskState:
    return TaskState(
        id=str(uuid.uuid4())[:8],
        title=title,
        status="pending",
        assigned_agent=assigned_agent,
        result=None,
    )


def _build_agents() -> Dict[str, Any]:
    return {
        "manager": ManagerAgent(),
        "dev_1": DeveloperAgent(agent_id="dev_1"),
        "qa_1": QaAgent(agent_id="qa_1"),
        "reviewer": ReviewerAgent(agent_id="reviewer"),
        "devops": DevOpsAgent(agent_id="devops"),
    }


def _build_payload(task: PlannedTask, artifacts: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(task.payload)
    repo_path = str(artifacts.get("repo_path", "")).strip()

    if task.task_type in {
        "inventory_workspace",
        "select_key_files",
        "summarize_key_files",
        "scan_and_report",
        "build_qa_findings",
        "review_outputs",
        "write_artifacts",
    }:
        payload["target_subdir"] = repo_path

    if task.task_type == "select_key_files":
        payload["workspace_metadata"] = artifacts.get("workspace_metadata", [])

    elif task.task_type == "summarize_key_files":
        payload["selected_files"] = artifacts.get("selected_files", [])

    elif task.task_type == "build_qa_findings":
        payload["workspace_files"] = artifacts.get("workspace_files", [])
        payload["workspace_metadata"] = artifacts.get("workspace_metadata", [])
        payload["selected_files"] = artifacts.get("selected_files", [])
        payload["report_md"] = artifacts.get("report_md", "")

    elif task.task_type == "review_outputs":
        payload["report_md"] = artifacts.get("report_md", "")
        payload["code_summary_md"] = artifacts.get("code_summary_md", "")
        payload["qa_findings_md"] = artifacts.get("qa_findings_md", "")

    elif task.task_type == "write_artifacts":
        payload["workspace_files"] = artifacts.get("workspace_files", [])
        payload["selected_files"] = artifacts.get("selected_files", [])
        payload["report_md"] = artifacts.get("report_md", "")
        payload["code_summary_md"] = artifacts.get("code_summary_md", "")
        payload["qa_findings_md"] = artifacts.get("qa_findings_md", "")
        payload["review_md"] = artifacts.get("review_md", "")

    return payload


def demo_run(repo_url: str | None = None) -> None:
    if get_run_in_progress():
        add_log("INFO", "orchestrator", "Run request ignored: run already in progress.")
        return

    set_run_in_progress(True)

    run_id = new_run_id()
    workspace_root = _ensure_workspace()
    ctx = ToolContext(workspace_root=workspace_root)
    artifacts: Dict[str, Any] = {}
    agents = _build_agents()
    manager = agents["manager"]
    current_task_id: str | None = None

    try:
        add_log(
            "INFO",
            "orchestrator",
            f"Run started | run_id={run_id} | workspace={workspace_root} | repo_url={repo_url or '[missing]'}",
        )
        snapshot_run(snapshot_for_api(), run_id, note="run_started")

        update_agent(
            "manager",
            status="working",
            current_task_id=None,
            last_action="Building task plan",
        )

        plan = manager.build_plan(repo_url=repo_url)

        update_agent(
            "manager",
            status="idle",
            current_task_id=None,
            last_action="Plan created",
        )

        for planned in plan:
            task = _new_task(planned.title, planned.assigned_agent)
            current_task_id = task.id

            upsert_task(task)
            update_task(task.id, status="in_progress")

            update_agent(
                planned.assigned_agent,
                status="working",
                current_task_id=task.id,
            )

            payload = _build_payload(planned, artifacts)
            agent = agents[planned.assigned_agent]
            result = agent.run_task(planned.task_type, ctx, payload)

            for key, value in result.items():
                if key != "result_message":
                    artifacts[key] = value

            result_message = str(result.get("result_message", "Done"))

            update_task(
                task.id,
                status="completed",
                result=result_message,
            )

            update_agent(
                planned.assigned_agent,
                status="idle",
                current_task_id=None,
                last_action=result_message,
            )

            add_log(
                "INFO",
                "orchestrator",
                f"Task completed | task_id={task.id} | agent={planned.assigned_agent} | message={result_message}",
            )

        add_log("INFO", "orchestrator", f"Run finished | run_id={run_id}")
        snapshot_run(snapshot_for_api(), run_id, note="run_finished")

    except Exception as e:
        add_log("ERROR", "orchestrator", f"Run failed | run_id={run_id} | error={e}")

        if current_task_id:
            try:
                update_task(current_task_id, status="failed", result=str(e))
            except Exception:
                pass

        for agent_key in ["manager", "dev_1", "qa_1", "reviewer", "devops"]:
            try:
                update_agent(
                    agent_key,
                    status="idle",
                    current_task_id=None,
                )
            except Exception:
                pass

        snapshot_run(snapshot_for_api(), run_id, note="run_failed")
        raise

    finally:
        set_run_in_progress(False)