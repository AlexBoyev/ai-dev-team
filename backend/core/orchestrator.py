from __future__ import annotations

import uuid
from pathlib import Path

from backend.core.memory import (
    add_log,
    get_run_in_progress,
    set_run_in_progress,
    update_agent,
    update_task,
    upsert_task,
    TaskState,
    snapshot_state,
)

from backend.core.persistence import new_run_id, snapshot_run
from backend.services.scanner_service import scan_directory, build_markdown_report
from backend.services.insights_service import analyze_workspace, append_insights_to_report
from backend.tools.file_tools import write_text


WORKSPACE_ROOT = Path("workspace")
REPORT_PATH = WORKSPACE_ROOT / "reports" / "latest_report.md"


def demo_run() -> None:
    if get_run_in_progress():
        return

    run_id = new_run_id()
    set_run_in_progress(True)

    try:
        add_log("INFO", "orchestrator", f"Run {run_id} started.")
        snapshot_run(snapshot_state(), run_id, note="run start")

        WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

        # -------------------------
        # Task 1: Scan workspace
        # -------------------------
        t_scan = str(uuid.uuid4())[:8]
        upsert_task(TaskState(
            id=t_scan,
            title="Scan workspace directory",
            status="pending",
            assigned_agent="dev_1"
        ))

        update_task(t_scan, status="in_progress")
        update_agent("dev_1", status="working", current_task_id=t_scan, last_action="Scanning workspace")
        add_log("INFO", "dev_1", f"Task {t_scan}: scanning `{WORKSPACE_ROOT}` ...")

        scan = scan_directory(WORKSPACE_ROOT)

        scan_summary = f"files={scan.total_files}, dirs={scan.total_dirs}, py={scan.python_files}"
        update_task(t_scan, status="completed", result=scan_summary)
        update_agent("dev_1", status="idle", current_task_id=None, last_action="Scan complete")
        add_log("INFO", "dev_1", f"Task {t_scan} completed: {scan_summary}")

        # -------------------------
        # Task 2: Write base report
        # -------------------------
        t_report = str(uuid.uuid4())[:8]
        upsert_task(TaskState(
            id=t_report,
            title="Write scan report to workspace/reports/latest_report.md",
            status="pending",
            assigned_agent="devops"
        ))

        update_task(t_report, status="in_progress")
        update_agent("devops", status="working", current_task_id=t_report, last_action="Writing report")
        add_log("INFO", "devops", f"Task {t_report}: writing report to `{REPORT_PATH}` ...")

        report_md = build_markdown_report(scan)
        write_text(REPORT_PATH, report_md)

        update_task(t_report, status="completed", result=f"Wrote {REPORT_PATH.as_posix()}")
        update_agent("devops", status="idle", current_task_id=None, last_action="Report written")
        add_log("INFO", "devops", f"Task {t_report} completed: report saved.")

        # -------------------------
        # Task 3: Insights analysis
        # -------------------------
        t_insights = str(uuid.uuid4())[:8]
        upsert_task(TaskState(
            id=t_insights,
            title="Analyze workspace for TODO/FIXME + suspicious strings + large files",
            status="pending",
            assigned_agent="qa_1"
        ))

        update_task(t_insights, status="in_progress")
        update_agent("qa_1", status="working", current_task_id=t_insights, last_action="Analyzing content")
        add_log("INFO", "qa_1", f"Task {t_insights}: analyzing `{WORKSPACE_ROOT}` for insights...")

        insights = analyze_workspace(WORKSPACE_ROOT)
        updated_report = append_insights_to_report(report_md, insights)
        write_text(REPORT_PATH, updated_report)

        insights_summary = f"todo_hits={insights.todo_hits}, suspicious_hits={insights.suspicious_hits}"
        update_task(t_insights, status="completed", result=insights_summary)
        update_agent("qa_1", status="idle", current_task_id=None, last_action="Insights complete")
        add_log("INFO", "qa_1", f"Task {t_insights} completed: {insights_summary}. Report updated.")

        add_log("INFO", "orchestrator", f"Run {run_id} finished successfully.")
        snapshot_run(snapshot_state(), run_id, note="run end")

    except Exception as e:
        add_log("ERROR", "orchestrator", f"Run {run_id} failed: {e}")
        snapshot_run(snapshot_state(), run_id, note="run failed")

    finally:
        set_run_in_progress(False)