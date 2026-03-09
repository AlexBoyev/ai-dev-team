from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ["DATABASE_URL"]

# NullPool is mandatory for Celery workers.
# Celery forks multiple processes — each must have its own
# connection and must NOT share a pool across process boundaries.
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Session:
    """
    FastAPI dependency injection — use with Depends(get_db).
    Yields a session and guarantees it is closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Direct session for Celery workers and orchestrator.
    Caller is responsible for calling db.close().
    """
    return SessionLocal()
