from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List

from backend.db.models import RunMemory


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def save_memory(
    db,
    repo_name: str,
    run_id: str,
    agent_key: str,
    memory_type: str,
    content: str,
) -> None:
    row = RunMemory(
        id=uuid.uuid4(),
        repo_name=repo_name,
        run_id=run_id,
        agent_key=agent_key,
        memory_type=memory_type,
        content=content,
        ts=utcnow(),
    )
    db.add(row)
    db.commit()


def load_memory(
    db,
    repo_name: str,
    agent_key: str | None = None,
    memory_type: str | None = None,
    limit: int = 10,
) -> List[dict[str, Any]]:
    query = db.query(RunMemory).filter(RunMemory.repo_name == repo_name)

    if agent_key:
        query = query.filter(RunMemory.agent_key == agent_key)
    if memory_type:
        query = query.filter(RunMemory.memory_type == memory_type)

    rows = (
        query.order_by(RunMemory.ts.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "repo_name": row.repo_name,
            "run_id": str(row.run_id),
            "agent_key": row.agent_key,
            "memory_type": row.memory_type,
            "content": row.content,
            "ts": row.ts.isoformat() if row.ts else None,
        }
        for row in rows
    ]
