from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "ai_dev_team",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["backend.tasks.pipeline_task"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Reliability
    task_track_started=True,
    task_acks_late=True,            # ACK only after task finishes → safe on worker crash
    worker_prefetch_multiplier=1,   # one task per worker slot at a time

    # Routing — all pipeline jobs go to the "pipeline" queue
    task_routes={
        "backend.tasks.pipeline_task.run_pipeline": {"queue": "pipeline"},
    },

    # Result expiry — keep results in Redis for 24 hours
    result_expires=86400,
)
