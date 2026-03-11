from __future__ import annotations
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
from backend.db.models import LLMCall
from sqlalchemy import func, extract
from backend.db.models import AgentEvent, Log, Run, Task, Artifact, utcnow
from backend.db.session import get_db
from backend.tasks.pipeline_task import run_pipeline

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

AGENT_KEYS = ["manager", "dev_1", "qa_1", "reviewer", "devops"]


class RunRequest(BaseModel):
    repo_url: str | None = None


@router.get("/api/tasks/{run_id}")
def api_tasks(run_id: str, db: Session = Depends(get_db)):
    tasks = (
        db.query(Task)
        .filter(Task.run_id == run_id)
        .order_by(Task.created_at)
        .all()
    )
    return JSONResponse([
        {
            "id": str(t.id),
            "title": t.title,
            "task_type": t.task_type if hasattr(t, "task_type") else "",
            "status": t.status,
            "assigned_agent": t.assigned_agent,
            "result": t.result,
        }
        for t in tasks
    ])


@router.get("/api/logs/{run_id}")
def api_logs(run_id: str, db: Session = Depends(get_db)):
    logs = (
        db.query(Log)
        .filter(Log.run_id == run_id)
        .order_by(Log.ts.asc())
        .limit(500)
        .all()
    )
    return JSONResponse([
        {
            "ts": l.ts.timestamp(),
            "level": l.level,
            "source": l.source,
            "message": l.message,
        }
        for l in logs
    ])


@router.get("/api/state")
def api_state(db: Session = Depends(get_db)):
    # Get most recent run (running OR completed/failed)
    latest_run = (
        db.query(Run)
        .order_by(Run.started_at.desc())
        .first()
    )

    # Separate flag for whether a run is actively in progress
    active_run = (
        db.query(Run)
        .filter(Run.status == "running")
        .order_by(Run.started_at.desc())
        .first()
    )

    run_in_progress = active_run is not None
    display_run = active_run or latest_run  # show latest if nothing running
    run_id = str(display_run.id) if display_run else None

    tasks = []
    agents = []
    logs = []

    if display_run:
        tasks = [
            {
                "id": str(t.id)[:8],
                "title": t.title,
                "status": t.status,
                "assigned_agent": t.assigned_agent,
                "result": t.result,
            }
            for t in db.query(Task)
            .filter(Task.run_id == display_run.id)
            .order_by(Task.created_at)
            .all()
        ]

        subq = (
            db.query(
                AgentEvent.agent_key,
                func.max(AgentEvent.ts).label("max_ts"),
            )
            .filter(AgentEvent.run_id == display_run.id)
            .group_by(AgentEvent.agent_key)
            .subquery()
        )
        agent_rows = (
            db.query(AgentEvent)
            .join(
                subq,
                (AgentEvent.agent_key == subq.c.agent_key)
                & (AgentEvent.ts == subq.c.max_ts),
            )
            .all()
        )

        event_lookup = {a.agent_key: a for a in agent_rows}
        agents = [
            {
                "name": key,
                "role": key,
                "status": event_lookup[key].status if key in event_lookup else "idle",
                "current_task_id": None,
                "last_action": event_lookup[key].action if key in event_lookup else None,
            }
            for key in AGENT_KEYS
        ]

        logs = [
            {
                "ts": l.ts.timestamp(),
                "level": l.level,
                "source": l.source,
                "message": l.message,
            }
            for l in db.query(Log)
            .filter(Log.run_id == display_run.id)
            .order_by(Log.ts.desc())
            .limit(250)
            .all()
        ]

    else:
        agents = [
            {
                "name": key,
                "role": key,
                "status": "idle",
                "current_task_id": None,
                "last_action": None,
            }
            for key in AGENT_KEYS
        ]

    return JSONResponse(
        {
            "run_in_progress": run_in_progress,
            "run_id": run_id,
            "agents": agents,
            "tasks": tasks,
            "logs": logs,
        }
    )


@router.post("/api/run")
def api_run(
    payload: RunRequest | None = None,
    db: Session = Depends(get_db),
):
    active = db.query(Run).filter(Run.status == "running").first()
    if active:
        return JSONResponse({"ok": True, "status": "already_running"})

    repo_url = None
    if payload:
        repo_url = (payload.repo_url or "").strip() or None

    if not repo_url:
        return JSONResponse(
            {"ok": False, "error": "repo_url is required"},
            status_code=400,
        )

    run = Run(
        id=uuid.uuid4(),
        status="running",
        repo_url=repo_url,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Dispatch to Celery and store task_id in run.note for cancellation
    celery_task = run_pipeline.apply_async(
        kwargs={"run_id": str(run.id), "repo_url": repo_url},
        queue="pipeline",
    )

    # Store celery task id so Reset can revoke it
    run.note = celery_task.id
    db.commit()

    return JSONResponse({"ok": True, "status": "started", "run_id": str(run.id)})


import shutil
from fastapi.responses import FileResponse, StreamingResponse
import zipfile
import io
from backend.db.models import Repository


@router.get("/api/repos")
def api_repos(db: Session = Depends(get_db)):
    """List all known repositories."""
    repos = db.query(Repository).order_by(Repository.cloned_at.desc()).all()
    return JSONResponse([
        {
            "id":         str(r.id),
            "name":       r.name,
            "url":        r.url,
            "local_path": r.local_path,
            "disk_bytes": r.disk_bytes,
            "cloned_at":  r.cloned_at.isoformat() if r.cloned_at else None,
            "last_run_id": str(r.last_run_id) if r.last_run_id else None,
        }
        for r in repos
    ])


@router.get("/api/costs")
def api_costs(db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    now    = datetime.now(timezone.utc)
    budget = float(os.environ.get("LLM_BUDGET_USD", "15.00"))

    monthly = db.query(
        func.sum(LLMCall.cost_usd).label("cost"),
        func.sum(LLMCall.total_tokens).label("tokens"),
        func.count(LLMCall.id).label("calls"),
    ).filter(
        extract("year",  LLMCall.ts) == now.year,
        extract("month", LLMCall.ts) == now.month,
    ).first()

    per_run = db.query(
        LLMCall.run_id,
        func.sum(LLMCall.cost_usd).label("cost"),
        func.sum(LLMCall.total_tokens).label("tokens"),
        func.count(LLMCall.id).label("calls"),
    ).filter(
        extract("year",  LLMCall.ts) == now.year,
        extract("month", LLMCall.ts) == now.month,
        LLMCall.run_id.isnot(None),
    ).group_by(LLMCall.run_id).order_by(func.sum(LLMCall.cost_usd).desc()).limit(20).all()

    per_model = db.query(
        LLMCall.model,
        func.sum(LLMCall.cost_usd).label("cost"),
        func.sum(LLMCall.total_tokens).label("tokens"),
    ).filter(
        extract("year",  LLMCall.ts) == now.year,
        extract("month", LLMCall.ts) == now.month,
    ).group_by(LLMCall.model).all()

    spent = float(monthly.cost or 0)

    return JSONResponse({
        "budget_usd":    budget,
        "spent_usd":     round(spent, 4),
        "remaining_usd": round(max(budget - spent, 0), 4),
        "percent_used":  round((spent / budget * 100) if budget > 0 else 0, 1),
        "total_tokens":  int(monthly.tokens or 0),
        "total_calls":   int(monthly.calls  or 0),
        "within_budget": spent < budget,
        "period":        now.strftime("%B %Y"),
        "per_run": [
            {
                "run_id":   str(r.run_id),
                "cost_usd": round(float(r.cost), 4),
                "tokens":   int(r.tokens),
                "calls":    int(r.calls),
            }
            for r in per_run
        ],
        "per_model": [
            {
                "model":    r.model,
                "cost_usd": round(float(r.cost), 4),
                "tokens":   int(r.tokens),
            }
            for r in per_model
        ],
    })


@router.post("/api/costs/refresh-pricing")
def api_refresh_pricing():
    """Force refresh of LLM pricing cache from litellm."""
    from backend.core.pricing import refresh_now
    count = refresh_now()
    return JSONResponse({"ok": True, "models_loaded": count})


@router.delete("/api/repos/{repo_id}")
def api_delete_repo(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        return JSONResponse({"error": "not found"}, status_code=404)

    # Delete from disk
    path = Path(repo.local_path)
    if path.exists():
        shutil.rmtree(path)

    # Find all runs for this repo URL
    run_ids_to_clean = [
        str(r.id) for r in
        db.query(Run).filter(Run.repo_url == repo.url).all()
    ]

    # ── Must null FK before deleting runs ───────────────────────
    repo.last_run_id = None
    db.commit()

    # Now safe to delete runs and all dependent rows
    for rid in run_ids_to_clean:
        db.query(Artifact).filter(Artifact.run_id == rid).delete()
        db.query(Log).filter(Log.run_id == rid).delete()
        db.query(Task).filter(Task.run_id == rid).delete()
        db.query(AgentEvent).filter(AgentEvent.run_id == rid).delete()
        db.query(Run).filter(Run.id == rid).delete()

        # Delete run artifact folder from disk
        run_artifact_path = Path("workspace") / "runs" / rid
        if run_artifact_path.exists():
            shutil.rmtree(run_artifact_path)

    db.commit()

    db.delete(repo)
    db.commit()

    return JSONResponse({"ok": True, "deleted": repo.name})




@router.get("/api/repos/{repo_id}/download")
def api_download_repo(repo_id: str, db: Session = Depends(get_db)):
    """Zip the repo folder and stream it to the browser."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        return JSONResponse({"error": "not found"}, status_code=404)

    path = Path(repo.local_path)
    if not path.exists():
        return JSONResponse({"error": "repo not on disk"}, status_code=404)

    # Build zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in path.rglob("*"):
            if file.is_file() and ".git" not in file.parts:
                zf.write(file, file.relative_to(path.parent))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={repo.name}.zip"},
    )


@router.get("/api/repos/{repo_id}/files")
def api_repo_files(repo_id: str, db: Session = Depends(get_db)):
    """List all files in a repo (excluding .git)."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        return JSONResponse({"error": "not found"}, status_code=404)

    path = Path(repo.local_path)
    if not path.exists():
        return JSONResponse([])

    files = [
        {
            "path": str(f.relative_to(path)),
            "size_bytes": f.stat().st_size,
        }
        for f in path.rglob("*")
        if f.is_file() and ".git" not in f.parts
    ]
    return JSONResponse(sorted(files, key=lambda x: x["path"]))


@router.post("/api/reset")
def api_reset(db: Session = Depends(get_db)):
    from backend.tasks.celery_app import celery_app

    # 1. Find all running runs
    running_runs = db.query(Run).filter(Run.status == "running").all()

    for run in running_runs:
        # 2. Revoke the Celery task if still in queue/executing
        # We stored the celery task id in run.note — see api_run below
        if run.note:
            celery_app.control.revoke(run.note, terminate=True, signal="SIGTERM")

        # 3. Mark run as failed
        run.status = "failed"
        run.finished_at = utcnow()

        # 4. Mark all pending/in_progress tasks as failed
        db.query(Task).filter(
            Task.run_id == run.id,
            Task.status.in_(["pending", "in_progress"]),
        ).update({"status": "failed", "result": "Reset by user"})

    db.commit()

    return JSONResponse({"ok": True})



@router.get("/api/runs")
def api_runs(db: Session = Depends(get_db), limit: int = 20):
    runs = (
        db.query(Run)
        .order_by(Run.started_at.desc())
        .limit(limit)
        .all()
    )
    return JSONResponse(
        [
            {
                "id": str(r.id),
                "status": r.status,
                "repo_url": r.repo_url,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ]
    )

@router.get("/api/artifacts/{run_id}")
def api_artifacts(run_id: str, db: Session = Depends(get_db)):
    artifacts = (
        db.query(Artifact)
        .filter(Artifact.run_id == run_id)
        .order_by(Artifact.name)
        .all()
    )
    return JSONResponse([
        {
            "id": str(a.id),
            "name": a.name,
            "size_bytes": a.size_bytes,
        }
        for a in artifacts
    ])


@router.get("/api/artifacts/{run_id}/{name}")
def api_artifact_content(run_id: str, name: str, db: Session = Depends(get_db)):
    artifact = (
        db.query(Artifact)
        .filter(Artifact.run_id == run_id, Artifact.name == name)
        .first()
    )
    if not artifact:
        return JSONResponse({"error": "not found"}, status_code=404)

    path = Path(artifact.path)
    if not path.exists():
        return JSONResponse({"error": "file missing from disk"}, status_code=404)

    return JSONResponse({"name": name, "content": path.read_text(encoding="utf-8")})

