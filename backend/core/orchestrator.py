# backend/core/orchestrator.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from backend.agents import DeveloperAgent, DevOpsAgent, QaAgent, ReviewerAgent
from backend.agents.manager import ManagerAgent
from backend.core.tasks import PlannedTask
from backend.db.models import AgentEvent, Artifact, Log, Repository, Run, Task
from backend.db.session import get_db_session
from backend.tools.tool_registry import ToolContext

WORKSPACE_ROOT = Path("workspace")

ARTIFACT_FILES = [
    "report.md",
    "code_summary.md",
    "qa_findings.md",
    "review.md",
    "final_summary.md",
    "repo_inventory.json",
    "selected_files.json",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_workspace() -> Path:
    root = WORKSPACE_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_artifact_dir(workspace_root: Path, run_id: str) -> Path:
    """Each run gets its own artifact folder so runs never overwrite each other."""
    d = workspace_root / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _add_log(db, run_id: str, level: str, source: str, message: str) -> None:
    db.add(Log(
        run_id=run_id,
        ts=utcnow(),
        level=level,
        source=source,
        message=message,
    ))
    db.commit()


def _update_agent(db, run_id: str, agent_key: str, status: str, action: str = "") -> None:
    db.add(AgentEvent(
        run_id=run_id,
        agent_key=agent_key,
        status=status,
        action=action,
        ts=utcnow(),
    ))
    db.commit()


def _build_agents() -> Dict[str, Any]:
    return {
        "manager":  ManagerAgent(),
        "dev_1":    DeveloperAgent(agent_id="dev_1"),
        "qa_1":     QaAgent(agent_id="qa_1"),
        "reviewer": ReviewerAgent(agent_id="reviewer"),
        "devops":   DevOpsAgent(agent_id="devops"),
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
        payload["workspace_files"]    = artifacts.get("workspace_files", [])
        payload["workspace_metadata"] = artifacts.get("workspace_metadata", [])
        payload["selected_files"]     = artifacts.get("selected_files", [])
        payload["report_md"]          = artifacts.get("report_md", "")

    elif task.task_type == "review_outputs":
        payload["report_md"]       = artifacts.get("report_md", "")
        payload["code_summary_md"] = artifacts.get("code_summary_md", "")
        payload["qa_findings_md"]  = artifacts.get("qa_findings_md", "")

    elif task.task_type == "write_artifacts":
        payload["workspace_files"]  = artifacts.get("workspace_files", [])
        payload["selected_files"]   = artifacts.get("selected_files", [])
        payload["report_md"]        = artifacts.get("report_md", "")
        payload["code_summary_md"]  = artifacts.get("code_summary_md", "")
        payload["qa_findings_md"]   = artifacts.get("qa_findings_md", "")
        payload["review_md"]        = artifacts.get("review_md", "")
        payload["artifact_dir"]     = str(artifacts.get("artifact_dir", ""))

    return payload


def _register_repo(
    db,
    run_id: str,
    repo_url: str,
    artifacts: Dict[str, Any],
    workspace_root: Path,
) -> None:
    repo_path_rel = (
        artifacts.get("repo_path")
        or artifacts.get("cloned_path")
        or artifacts.get("path")
        or artifacts.get("result_path")
        or ""
    )
    repo_path_rel = str(repo_path_rel).strip()

    if not repo_path_rel and repo_url:
        repo_name = repo_url.rstrip("/").split("/")[-1]
        repo_path_rel = f"repos/{repo_name}"

    if not repo_path_rel:
        return

    full_path = workspace_root / repo_path_rel
    name = full_path.name

    disk_bytes = 0
    if full_path.exists():
        disk_bytes = sum(
            f.stat().st_size
            for f in full_path.rglob("*")
            if f.is_file() and ".git" not in f.parts
        )

    existing = db.query(Repository).filter(Repository.name == name).first()
    if existing:
        existing.disk_bytes  = disk_bytes
        existing.last_run_id = run_id
        existing.updated_at  = utcnow()
    else:
        db.add(Repository(
            name=name,
            url=repo_url,
            local_path=str(full_path),
            disk_bytes=disk_bytes,
            last_run_id=run_id,
            cloned_at=utcnow(),
            updated_at=utcnow(),
        ))

    db.commit()


def _register_artifacts(
    db,
    run_id: str,
    artifact_dir: Path,
) -> None:
    """
    Register output files from the run-specific artifact_dir.
    Each run writes to workspace/runs/{run_id}/ so files never collide.
    """
    for name in ARTIFACT_FILES:
        path = artifact_dir / name
        if not path.exists():
            continue

        already = (
            db.query(Artifact)
            .filter(Artifact.run_id == run_id, Artifact.name == name)
            .first()
        )
        if already:
            continue

        db.add(Artifact(
            run_id=run_id,
            name=name,
            path=str(path),
            size_bytes=path.stat().st_size,
        ))

    db.commit()


def demo_run(run_id: str, repo_url: str | None = None) -> None:
    db = get_db_session()

    try:
        workspace_root = _ensure_workspace()
        artifact_dir   = _run_artifact_dir(workspace_root, run_id)

        # Pass db + run_id so agents can call llm_client.complete() via _call_llm()
        ctx = ToolContext(
            workspace_root=workspace_root,
            db=db,
            run_id=run_id,
        )

        artifacts: Dict[str, Any] = {
            "artifact_dir": str(artifact_dir),
        }
        agents  = _build_agents()
        manager = agents["manager"]
        current_task_db_id: str | None = None

        _add_log(db, run_id, "INFO", "orchestrator",
                 f"Run started | run_id={run_id} | repo_url={repo_url or '[missing]'}")

        # ── Manager builds the plan ──────────────────────────────────────
        _update_agent(db, run_id, "manager", "working", "Building task plan")
        plan = manager.build_plan(repo_url=repo_url)
        _update_agent(db, run_id, "manager", "idle", "Plan created")

        # ── Execute each planned task ────────────────────────────────────
        for planned in plan:

            task_db_id         = str(uuid.uuid4())
            current_task_db_id = task_db_id

            task_row = Task(
                id=task_db_id,
                run_id=run_id,
                title=planned.title,
                task_type=planned.task_type,
                assigned_agent=planned.assigned_agent,
                status="pending",
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(task_row)
            db.commit()

            task_row.status     = "in_progress"
            task_row.updated_at = utcnow()
            db.commit()

            _update_agent(db, run_id, planned.assigned_agent,
                          "working", f"Starting: {planned.title}")

            payload = _build_payload(planned, artifacts)
            agent   = agents[planned.assigned_agent]
            result  = agent.run_task(planned.task_type, ctx, payload)

            for key, value in result.items():
                if key != "result_message":
                    artifacts[key] = value

            result_message = str(result.get("result_message", "Done"))

            task_row.status     = "completed"
            task_row.result     = result_message
            task_row.updated_at = utcnow()
            db.commit()

            _update_agent(db, run_id, planned.assigned_agent, "idle", result_message)

            _add_log(db, run_id, "INFO", "orchestrator",
                     f"Task completed | agent={planned.assigned_agent} | {result_message}")

            # ── Post-task hooks ──────────────────────────────────────────

            if planned.task_type == "clone_repository":
                _add_log(db, run_id, "INFO", "orchestrator",
                         f"Clone result keys: {list(result.keys())} | "
                         f"values: {dict(list(result.items())[:5])}")
                _register_repo(db, run_id, repo_url or "", artifacts, workspace_root)

            if planned.task_type == "write_artifacts":
                _register_artifacts(db, run_id, artifact_dir)

        # ── Mark run completed ───────────────────────────────────────────
        run_row = db.query(Run).filter(Run.id == run_id).first()
        if run_row:
            run_row.status      = "completed"
            run_row.finished_at = utcnow()
            db.commit()

        _add_log(db, run_id, "INFO", "orchestrator",
                 f"Run finished | run_id={run_id}")

    except Exception as e:
        _add_log(db, run_id, "ERROR", "orchestrator",
                 f"Run failed | run_id={run_id} | error={e}")

        if current_task_db_id:
            try:
                t = db.query(Task).filter(Task.id == current_task_db_id).first()
                if t:
                    t.status     = "failed"
                    t.result     = str(e)
                    t.updated_at = utcnow()
                    db.commit()
            except Exception:
                pass

        try:
            run_row = db.query(Run).filter(Run.id == run_id).first()
            if run_row:
                run_row.status      = "failed"
                run_row.finished_at = utcnow()
                db.commit()
        except Exception:
            pass

        raise

    finally:
        db.close()
