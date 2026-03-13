from __future__ import annotations

from backend.tasks.celery_app import celery_app


@celery_app.task(
    name="backend.tasks.pipeline_task.run_pipeline",
    max_retries=0,
    acks_late=True,
)
def run_pipeline(run_id: str, repo_url: str | None = None, resume: bool = False) -> dict:
    from backend.core.orchestrator import demo_run

    try:
        demo_run(
            run_id=run_id,
            repo_url=repo_url,
            resume_from="auto" if resume else None,
        )
        return {"status": "completed", "run_id": run_id}
    except Exception as e:
        return {"status": "failed", "run_id": run_id, "error": str(e)}
