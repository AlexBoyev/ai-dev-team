from __future__ import annotations

import os
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from backend.agents import DeveloperAgent, DevOpsAgent, QaAgent, ReviewerAgent
from backend.agents.manager import ManagerAgent
from backend.core.tasks import PlannedTask
from backend.db.models import AgentEvent, Artifact, Log, Repository, Run, Task
from backend.db.session import get_db_session
from backend.tools.tool_registry import ToolContext

WORKSPACE_ROOT      = Path("workspace")
MAX_FIX_ITERATIONS  = int(os.environ.get("MAX_FIX_ITERATIONS",        "3"))
AUTO_APPROVE_FIXES  = os.environ.get("AUTO_APPROVE_FIXES",            "false").lower() == "true"
APPROVAL_TIMEOUT    = int(os.environ.get("APPROVAL_TIMEOUT_SECONDS",  "1800"))

# Phase 1/2 task types that can be reused from a previous completed run
REUSABLE_TASK_TYPES = {
    "clone_repository",
    "inventory_workspace",
    "select_key_files",
    "summarize_key_files",
    "scan_and_report",
    "build_qa_findings",
    "review_outputs",
    "write_artifacts",
}

ARTIFACT_FILES = [
    "report.md",
    "code_summary.md",
    "qa_findings.md",
    "review.md",
    "final_summary.md",
    "repo_inventory.json",
    "selected_files.json",
    "fix_diff_iter1.diff",
    "fix_diff_iter2.diff",
    "fix_diff_iter3.diff",
    "test_results_iter1.txt",
    "test_results_iter2.txt",
    "test_results_iter3.txt",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_workspace() -> Path:
    root = WORKSPACE_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _run_artifact_dir(workspace_root: Path, run_id: str) -> Path:
    d = workspace_root / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _add_log(db, run_id: str, level: str, source: str, message: str) -> None:
    db.add(Log(run_id=run_id, ts=utcnow(), level=level, source=source, message=message))
    db.commit()


def _update_agent(db, run_id: str, agent_key: str, status: str, action: str = "") -> None:
    db.add(AgentEvent(run_id=run_id, agent_key=agent_key, status=status, action=action, ts=utcnow()))
    db.commit()


def _build_agents() -> Dict[str, Any]:
    return {
        "manager":  ManagerAgent(),
        "dev_1":    DeveloperAgent(agent_id="dev_1"),
        "qa_1":     QaAgent(agent_id="qa_1"),
        "reviewer": ReviewerAgent(agent_id="reviewer"),
        "devops":   DevOpsAgent(agent_id="devops"),
    }


def _create_task_row(db, run_id: str, planned: PlannedTask, iteration: int = 0) -> str:
    task_db_id = str(uuid.uuid4())
    db.add(Task(
        id=task_db_id,
        run_id=run_id,
        title=planned.title,
        task_type=planned.task_type,
        assigned_agent=planned.assigned_agent,
        status="pending",
        iteration=iteration,
        created_at=utcnow(),
        updated_at=utcnow(),
    ))
    db.commit()
    return task_db_id


def _run_single_task(
    db,
    run_id: str,
    planned: PlannedTask,
    agents: Dict[str, Any],
    ctx: ToolContext,
    payload: Dict[str, Any],
    iteration: int = 0,
    existing_task_id: str | None = None,
) -> tuple[Dict[str, Any], str]:
    task_db_id  = existing_task_id or _create_task_row(db, run_id, planned, iteration)
    ctx.task_id = task_db_id

    task_row            = db.query(Task).filter(Task.id == task_db_id).first()
    task_row.status     = "in_progress"
    task_row.updated_at = utcnow()
    db.commit()

    _update_agent(db, run_id, planned.assigned_agent, "working", f"Starting: {planned.title}")

    timeout_seconds = int(os.environ.get("MAX_TASK_TIMEOUT_SECONDS", "300"))
    agent           = agents[planned.assigned_agent]

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(agent.run_task, planned.task_type, ctx, payload)
        try:
            result = future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            raise RuntimeError(f"Task timed out after {timeout_seconds}s: {planned.title}")

    result_message      = str(result.get("result_message", "Done"))
    task_row.status     = "completed"
    task_row.result     = result_message
    task_row.updated_at = utcnow()
    db.commit()

    _update_agent(db, run_id, planned.assigned_agent, "idle", result_message)
    _add_log(db, run_id, "INFO", "orchestrator",
             f"Task completed | agent={planned.assigned_agent} | {result_message}")

    return result, task_db_id


def _build_payload(
    task_type: str,
    artifacts: Dict[str, Any],
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload   = dict(extra or {})
    repo_path = str(artifacts.get("repo_path", "")).strip()

    if task_type in {
        "inventory_workspace", "select_key_files", "summarize_key_files",
        "scan_and_report", "build_qa_findings", "review_outputs",
        "write_artifacts", "generate_fix", "run_tests", "review_diff",
    }:
        payload["target_subdir"] = repo_path

    payload["artifact_dir"] = str(artifacts.get("artifact_dir", ""))

    if task_type == "select_key_files":
        payload["workspace_metadata"] = artifacts.get("workspace_metadata", [])
    elif task_type == "summarize_key_files":
        payload["selected_files"] = artifacts.get("selected_files", [])
    elif task_type == "scan_and_report":
        payload["workspace_files"] = artifacts.get("workspace_files", [])
    elif task_type == "build_qa_findings":
        payload.update({
            "workspace_files":    artifacts.get("workspace_files",    []),
            "workspace_metadata": artifacts.get("workspace_metadata", []),
            "selected_files":     artifacts.get("selected_files",     []),
            "report_md":          artifacts.get("report_md",          ""),
        })
    elif task_type == "review_outputs":
        payload.update({
            "report_md":       artifacts.get("report_md",       ""),
            "code_summary_md": artifacts.get("code_summary_md", ""),
            "qa_findings_md":  artifacts.get("qa_findings_md",  ""),
        })
    elif task_type == "write_artifacts":
        payload.update({
            "workspace_files":  artifacts.get("workspace_files",  []),
            "selected_files":   artifacts.get("selected_files",   []),
            "report_md":        artifacts.get("report_md",        ""),
            "code_summary_md":  artifacts.get("code_summary_md",  ""),
            "qa_findings_md":   artifacts.get("qa_findings_md",   ""),
            "review_md":        artifacts.get("review_md",        ""),
        })
    elif task_type == "generate_fix":
        payload.update({
            "qa_findings_md": artifacts.get("qa_findings_md", ""),
            "selected_files": artifacts.get("selected_files", []),
        })
    elif task_type == "run_tests":
        pass
    elif task_type == "review_diff":
        payload.update({
            "fix_diff":       artifacts.get("fix_diff",       ""),
            "qa_findings_md": artifacts.get("qa_findings_md", ""),
            "test_output":    artifacts.get("test_output",    ""),
            "tests_passed":   artifacts.get("tests_passed",   False),
            "auto_approve":   AUTO_APPROVE_FIXES,
        })

    return payload


def _check_disk_quota(workspace_root: Path) -> None:
    limit_mb   = int(os.environ.get("MAX_DISK_MB", "500"))
    used_bytes = sum(f.stat().st_size for f in workspace_root.rglob("*") if f.is_file())
    if used_bytes > limit_mb * 1024 * 1024:
        raise RuntimeError(
            f"Disk quota exceeded: {used_bytes // (1024 * 1024)}MB > {limit_mb}MB"
        )


def _register_repo(db, run_id, repo_url, artifacts, workspace_root) -> None:
    repo_path_rel = str(artifacts.get("repo_path", "")).strip()
    if not repo_path_rel and repo_url:
        repo_name     = repo_url.rstrip("/").split("/")[-1]
        repo_path_rel = f"repos/{repo_name}"
    if not repo_path_rel:
        return

    full_path  = workspace_root / repo_path_rel
    name       = full_path.name
    disk_bytes = 0
    if full_path.exists():
        disk_bytes = sum(
            f.stat().st_size for f in full_path.rglob("*")
            if f.is_file() and ".git" not in f.parts
        )

    existing = db.query(Repository).filter(Repository.name == name).first()
    if existing:
        existing.disk_bytes  = disk_bytes
        existing.last_run_id = run_id
        existing.updated_at  = utcnow()
    else:
        db.add(Repository(
            name=name, url=repo_url, local_path=str(full_path),
            disk_bytes=disk_bytes, last_run_id=run_id,
            cloned_at=utcnow(), updated_at=utcnow(),
        ))
    db.commit()


def _reload_artifacts_from_disk(artifacts: Dict[str, Any], artifact_dir: Path) -> None:
    import json

    mapping = {
        "report_md":       "report.md",
        "code_summary_md": "code_summary.md",
        "qa_findings_md":  "qa_findings.md",
        "review_md":       "review.md",
    }
    for key, filename in mapping.items():
        path = artifact_dir / filename
        if path.exists() and not artifacts.get(key):
            artifacts[key] = path.read_text(encoding="utf-8", errors="replace")

    for json_name, key in [
        ("repo_inventory.json", "workspace_files"),
        ("selected_files.json", "selected_files"),
    ]:
        path = artifact_dir / json_name
        if path.exists() and not artifacts.get(key):
            try:
                artifacts[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass

    if not artifacts.get("repo_path"):
        repos_dir = artifact_dir.parent.parent.parent / "repos"
        if repos_dir.exists():
            repos = [p for p in repos_dir.glob("*") if p.is_dir()]
            if repos:
                artifacts["repo_path"] = f"repos/{repos[0].name}"


def _register_artifacts(db, run_id: str, artifact_dir: Path) -> None:
    all_names = ARTIFACT_FILES + [
        f for f in [p.name for p in artifact_dir.glob("*")]
        if f not in ARTIFACT_FILES and (
            f.endswith(".diff") or f.endswith(".md") or f.endswith(".txt")
        )
    ]
    for name in all_names:
        path = artifact_dir / name
        if not path.exists():
            continue
        already = db.query(Artifact).filter(
            Artifact.run_id == run_id, Artifact.name == name
        ).first()
        if already:
            already.size_bytes = path.stat().st_size
        else:
            db.add(Artifact(
                run_id=run_id, name=name,
                path=str(path), size_bytes=path.stat().st_size,
            ))
    db.commit()


def _find_prev_completed_run(db, repo_url: str, current_run_id: str) -> Run | None:
    """Return the most recent completed run for the same repo, excluding the current run."""
    return (
        db.query(Run)
        .filter(
            Run.repo_url == repo_url,
            Run.status   == "completed",
            Run.id       != current_run_id,
        )
        .order_by(Run.started_at.desc())
        .first()
    )


def _copy_artifacts_from_prev_run(
    prev_artifact_dir: Path,
    artifact_dir: Path,
) -> None:
    """Copy Phase 1/2 artifact files from a previous run into the current run dir."""
    if not prev_artifact_dir.exists():
        return
    phase_files = {
        "report.md", "code_summary.md", "qa_findings.md", "review.md",
        "final_summary.md", "repo_inventory.json", "selected_files.json",
    }
    for name in phase_files:
        src  = prev_artifact_dir / name
        dest = artifact_dir / name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)


# ── Human approval gate ────────────────────────────────────────────────────────

def _await_human_approval(db, run_id: str, review_task_db_id: str, iteration: int) -> bool:
    run_row = db.query(Run).filter(Run.id == run_id).first()
    if run_row:
        run_row.awaiting_approval = True
        db.commit()

    _add_log(db, run_id, "INFO", "orchestrator",
             f"⏳ Awaiting human approval for iteration {iteration} "
             f"(timeout={APPROVAL_TIMEOUT}s)...")

    elapsed  = 0
    interval = 3
    approved = None

    while elapsed < APPROVAL_TIMEOUT:
        time.sleep(interval)
        elapsed += interval
        db.expire_all()
        task_check = db.query(Task).filter(Task.id == review_task_db_id).first()
        if task_check and task_check.approved is not None:
            approved = task_check.approved
            break

    if approved is None:
        _add_log(db, run_id, "WARN", "orchestrator",
                 f"⚠️ Approval timed out after {APPROVAL_TIMEOUT}s — treating as rejected")
        approved = False

    run_row = db.query(Run).filter(Run.id == run_id).first()
    if run_row:
        run_row.awaiting_approval = False
        db.commit()

    return approved


# ── Fix iteration loop ─────────────────────────────────────────────────────────

def _run_fix_loop(
    db,
    run_id: str,
    agents: Dict[str, Any],
    ctx: ToolContext,
    artifacts: Dict[str, Any],
    artifact_dir: Path,
) -> None:
    from backend.core.tasks import PlannedTask as PT

    _add_log(db, run_id, "INFO", "orchestrator",
             f"Starting fix loop | max_iterations={MAX_FIX_ITERATIONS} | "
             f"auto_approve={AUTO_APPROVE_FIXES}")

    for iteration in range(1, MAX_FIX_ITERATIONS + 1):
        run_row = db.query(Run).filter(Run.id == run_id).first()
        if run_row:
            run_row.current_iteration = iteration
            db.commit()

        _add_log(db, run_id, "INFO", "orchestrator",
                 f"── Fix iteration {iteration}/{MAX_FIX_ITERATIONS} ──")

        # ── 1. Generate fix ───────────────────────────────────────────
        fix_task = PT(
            title=f"Generate fix (iter {iteration})",
            task_type="generate_fix",
            assigned_agent="dev_1",
            payload={"iteration": iteration, "past_failures": artifacts.get("past_failures", [])},
        )
        fix_payload = _build_payload("generate_fix", artifacts, dict(fix_task.payload))
        fix_result, _ = _run_single_task(
            db, run_id, fix_task, agents, ctx, fix_payload, iteration
        )
        artifacts.update({k: v for k, v in fix_result.items() if k != "result_message"})

        # Register diff immediately so the UI can fetch it before approval
        _register_artifacts(db, run_id, artifact_dir)

        # ── 2. Run tests ──────────────────────────────────────────────
        test_task = PT(
            title=f"Run tests (iter {iteration})",
            task_type="run_tests",
            assigned_agent="qa_1",
            payload={"iteration": iteration},
        )
        test_payload = _build_payload("run_tests", artifacts, dict(test_task.payload))
        test_result, _ = _run_single_task(
            db, run_id, test_task, agents, ctx, test_payload, iteration
        )
        artifacts.update({k: v for k, v in test_result.items() if k != "result_message"})

        # ── 3. Review diff ────────────────────────────────────────────
        review_task = PT(
            title=f"Review diff (iter {iteration})",
            task_type="review_diff",
            assigned_agent="reviewer",
            payload={"iteration": iteration},
        )

        if AUTO_APPROVE_FIXES:
            review_payload = _build_payload("review_diff", artifacts, dict(review_task.payload))
            review_result, _ = _run_single_task(
                db, run_id, review_task, agents, ctx, review_payload, iteration
            )
            artifacts.update({k: v for k, v in review_result.items() if k != "result_message"})
            approved = bool(review_result.get("approved", False))

        else:
            # Human gate
            review_task_db_id = _create_task_row(db, run_id, review_task, iteration)

            task_row            = db.query(Task).filter(Task.id == review_task_db_id).first()
            task_row.status     = "in_progress"
            task_row.updated_at = utcnow()
            db.commit()

            _update_agent(db, run_id, "reviewer", "waiting", "Awaiting human approval")

            approved = _await_human_approval(db, run_id, review_task_db_id, iteration)

            task_row            = db.query(Task).filter(Task.id == review_task_db_id).first()
            task_row.status     = "completed"
            task_row.result     = "Approved ✅" if approved else "Rejected ❌"
            task_row.approved   = approved
            task_row.updated_at = utcnow()
            db.commit()

            _update_agent(db, run_id, "reviewer", "idle",
                          "Approved ✅" if approved else "Rejected ❌")
            _add_log(db, run_id, "INFO", "orchestrator",
                     f"Human decision for iter {iteration}: {'approved' if approved else 'rejected'}")

            artifacts["approved"] = approved

        tests_passed = artifacts.get("tests_passed", False)

        if approved and tests_passed:
            _add_log(db, run_id, "INFO", "orchestrator",
                     f"✅ Fix approved and tests passed at iteration {iteration}")
            break

        reason = "rejected by reviewer" if not approved else "tests still failing"
        _add_log(db, run_id, "INFO", "orchestrator",
                 f"Iteration {iteration} {reason} — trying next iteration")

        past = artifacts.get("past_failures", [])
        past.append({
            "iteration":   iteration,
            "test_output": artifacts.get("test_output", "")[:500],
            "approved":    approved,
        })
        artifacts["past_failures"] = past

    _register_artifacts(db, run_id, artifact_dir)


# ── Main entry point ───────────────────────────────────────────────────────────

def demo_run(run_id: str, repo_url: str | None = None, resume_from: str | None = None) -> None:
    db = get_db_session()

    try:
        workspace_root = _ensure_workspace()
        artifact_dir   = _run_artifact_dir(workspace_root, run_id)

        ctx = ToolContext(
            workspace_root=workspace_root,
            db=db,
            run_id=run_id,
            task_id=None,
        )

        artifacts: Dict[str, Any] = {"artifact_dir": str(artifact_dir)}
        agents = _build_agents()

        _add_log(db, run_id, "INFO", "orchestrator",
                 f"Run started | run_id={run_id} | repo_url={repo_url or '[missing]'}")

        # ── Find previous completed run for same repo ────────────────
        prev_run          = _find_prev_completed_run(db, repo_url or "", run_id) if repo_url else None
        prev_artifact_dir = _run_artifact_dir(workspace_root, str(prev_run.id)) if prev_run else None

        if prev_run:
            _add_log(db, run_id, "INFO", "orchestrator",
                     f"Found previous completed run {str(prev_run.id)[:8]} — "
                     f"will reuse Phase 1/2 artifacts")
            _copy_artifacts_from_prev_run(prev_artifact_dir, artifact_dir)

        # ── Phase 1 & 2: Analysis pipeline ──────────────────────────
        _update_agent(db, run_id, "manager", "working", "Building task plan")
        plan = agents["manager"].build_plan(repo_url=repo_url)
        _update_agent(db, run_id, "manager", "idle", "Plan created")

        for planned in plan:
            # Check current run first
            existing = db.query(Task).filter(
                Task.run_id    == run_id,
                Task.task_type == planned.task_type,
                Task.status    == "completed",
            ).first()

            # Then check previous completed run for same repo
            if not existing and prev_run and planned.task_type in REUSABLE_TASK_TYPES:
                existing = db.query(Task).filter(
                    Task.run_id    == str(prev_run.id),
                    Task.task_type == planned.task_type,
                    Task.status    == "completed",
                ).first()
                if existing:
                    # Mirror the task into the current run so UI shows it
                    db.add(Task(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        title=planned.title,
                        task_type=planned.task_type,
                        assigned_agent=planned.assigned_agent,
                        status="completed",
                        iteration=0,
                        result=f"Reused from previous run ({str(prev_run.id)[:8]})",
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    ))
                    db.commit()

            if existing:
                _add_log(db, run_id, "INFO", "orchestrator",
                         f"Skipping completed task: {planned.task_type}")
                _reload_artifacts_from_disk(artifacts, artifact_dir)
                continue

            payload   = _build_payload(planned.task_type, artifacts, dict(planned.payload))
            result, _ = _run_single_task(db, run_id, planned, agents, ctx, payload)

            for key, value in result.items():
                if key != "result_message":
                    artifacts[key] = value

            if planned.task_type == "clone_repository":
                _add_log(db, run_id, "INFO", "orchestrator",
                         f"Clone result: {dict(list(result.items())[:5])}")
                _register_repo(db, run_id, repo_url or "", artifacts, workspace_root)

            if planned.task_type == "write_artifacts":
                _register_artifacts(db, run_id, artifact_dir)

            _check_disk_quota(workspace_root)

        # Ensure artifacts are loaded before fix loop
        _reload_artifacts_from_disk(artifacts, artifact_dir)

        # ── Phase 3: Fix iteration loop ──────────────────────────────
        enable_fix_loop = os.environ.get("ENABLE_FIX_LOOP", "false").lower() == "true"

        if enable_fix_loop and artifacts.get("qa_findings_md"):
            _run_fix_loop(db, run_id, agents, ctx, artifacts, artifact_dir)

        # ── Finalize ─────────────────────────────────────────────────
        run_row = db.query(Run).filter(Run.id == run_id).first()
        if run_row:
            run_row.status            = "completed"
            run_row.finished_at       = utcnow()
            run_row.awaiting_approval = False
            db.commit()

        _add_log(db, run_id, "INFO", "orchestrator", f"Run finished | run_id={run_id}")

    except Exception as e:
        _add_log(db, run_id, "ERROR", "orchestrator",
                 f"Run failed | run_id={run_id} | error={e}")
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
