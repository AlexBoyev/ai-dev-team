from __future__ import annotations

from backend.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="backend.tasks.pipeline_task.run_pipeline",
    max_retries=0,    # never auto-retry agent pipelines — side effects are not idempotent
    acks_late=True,
)
def run_pipeline(self, run_id: str, repo_url: str | None = None) -> dict:
    # Import here to avoid circular imports at module load time
    from backend.core.orchestrator import demo_run

    try:
        demo_run(run_id=run_id, repo_url=repo_url)
        return {"status": "completed", "run_id": run_id}
    except Exception as e:
        return {"status": "failed", "run_id": run_id, "error": str(e)}
