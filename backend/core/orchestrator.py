from __future__ import annotations

import uuid
from pathlib import Path

from backend.agents import DeveloperAgent, DevOpsAgent, QaAgent
from backend.core.memory import (
    TaskState,
    add_log,
    get_run_in_progress,
    set_run_in_progress,
    snapshot_state,
    update_agent,
    update_task,
    upsert_task,
)
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


def demo_run() -> None:
    if get_run_in_progress():
        add_log("INFO", "orchestrator", "Run request ignored: run already in progress.")
        return

    set_run_in_progress(True)
    run_id = str(uuid.uuid4())
    workspace_root = _ensure_workspace()
    ctx = ToolContext(workspace_root=workspace_root)

    dev = DeveloperAgent(agent_id="dev_1")
    qa = QaAgent(agent_id="qa_1")
    devops = DevOpsAgent(agent_id="devops")

    try:
        add_log(
            "INFO",
            "orchestrator",
            f"Run started | run_id={run_id} | workspace={workspace_root}",
        )

        update_agent(
            "dev_1",
            status="idle",
            current_task_id=None,
            last_action=None,
        )
        update_agent(
            "qa_1",
            status="idle",
            current_task_id=None,
            last_action=None,
        )
        update_agent(
            "devops",
            status="idle",
            current_task_id=None,
            last_action=None,
        )

        # ---------------------------
        # Task 1: developer scan/report
        # ---------------------------
        t1 = _new_task(
            "Analyze workspace for TODO/FIXME + suspicious strings + large files",
            "dev_1",
        )
        upsert_task(t1)

        update_task(t1.id, status="in_progress")
        update_agent("dev_1", status="working", current_task_id=t1.id)

        scan_out = dev.run_task("scan", ctx)
        scan_result = scan_out["scan_result"]

        report_out = dev.run_task("build_report", ctx, {"scan_result": scan_result})
        report_md = report_out["report_md"]

        update_task(t1.id, status="completed", result="Scan complete")
        update_agent(
            "dev_1",
            status="idle",
            current_task_id=None,
            last_action="Scan complete",
        )
        add_log(
            "INFO",
            "orchestrator",
            f"Developer scan/report completed | task_id={t1.id}",
        )

        # ---------------------------
        # Task 2: QA insights
        # ---------------------------
        t2 = _new_task("Generate insights summary", "qa_1")
        upsert_task(t2)

        update_task(t2.id, status="in_progress")
        update_agent("qa_1", status="working", current_task_id=t2.id)

        insights_out = qa.run_task("insights", ctx)
        insights = insights_out["insights"]

        report_out2 = qa.run_task(
            "append_insights",
            ctx,
            {"report_md": report_md, "insights": insights},
        )
        report_md = report_out2["report_md"]

        update_task(t2.id, status="completed", result="Insights complete")
        update_agent(
            "qa_1",
            status="idle",
            current_task_id=None,
            last_action="Insights complete",
        )
        add_log(
            "INFO",
            "orchestrator",
            f"QA insights completed | task_id={t2.id}",
        )

        # ---------------------------
        # Task 3: DevOps write report
        # ---------------------------
        t3 = _new_task("Write report to workspace and persist snapshot", "devops")
        upsert_task(t3)

        update_task(t3.id, status="in_progress")
        update_agent("devops", status="working", current_task_id=t3.id)

        devops_out = devops.run_task("write_report", ctx, {"report_md": report_md})
        written_file = devops_out.get("written", "workspace/report.md")

        update_task(t3.id, status="completed", result=written_file)
        update_agent(
            "devops",
            status="idle",
            current_task_id=None,
            last_action="Report written",
        )
        add_log(
            "INFO",
            "orchestrator",
            f"DevOps write completed | task_id={t3.id} | file={written_file}",
        )

        snapshot_state()

        add_log(
            "INFO",
            "orchestrator",
            f"Run finished | run_id={run_id}",
        )

    except Exception as e:
        add_log(
            "ERROR",
            "orchestrator",
            f"Run failed | run_id={run_id} | error={e}",
        )

        # Best effort recovery for UI state
        try:
            update_agent("dev_1", status="idle", current_task_id=None)
            update_agent("qa_1", status="idle", current_task_id=None)
            update_agent("devops", status="idle", current_task_id=None)
        except Exception:
            pass

        # Mark any in-progress tasks as failed
        try:
            for task_id in ["t1", "t2", "t3"]:
                if task_id in locals():
                    task_obj = locals()[task_id]
                    if task_obj is not None:
                        update_task(task_obj.id, status="failed", result=str(e))
        except Exception:
            pass

        raise

    finally:
        set_run_in_progress(False)