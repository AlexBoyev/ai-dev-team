from __future__ import annotations

import logging
from fastapi import FastAPI
from backend.api.routes import router


class _CleanAccessLog(logging.Filter):
    """
    Suppress noisy uvicorn log lines:
    - GET /api/state polling spam
    - The internal 0.0.0.0:8010 startup message
    """
    _SUPPRESS = (
        "GET /api/state",
        "0.0.0.0:8010",
        "http://0.0.0.0",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(s in msg for s in self._SUPPRESS)


logging.getLogger("uvicorn.access").addFilter(_CleanAccessLog())
logging.getLogger("uvicorn.error").addFilter(_CleanAccessLog())

app = FastAPI(title="AI Dev Team API")
app.include_router(router)
