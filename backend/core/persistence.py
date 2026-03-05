from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

DATA_DIR = Path("data")
RUNS_DIR = DATA_DIR / "runs"
STATE_FILE = DATA_DIR / "state.json"
LOG_FILE = DATA_DIR / "logs.jsonl"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state() -> Optional[Dict[str, Any]]:
    """
    Loads persisted app state (agents/tasks/run_in_progress).
    Returns None if no state exists yet.
    """
    ensure_data_dirs()
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        # Corrupted file -> don't crash boot
        return None


def save_state(state: Dict[str, Any]) -> None:
    """
    Atomically writes state.json.
    """
    ensure_data_dirs()
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


def append_log(level: str, source: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
    """
    Appends one log line as JSONL.
    """
    ensure_data_dirs()
    event: Dict[str, Any] = {
        "ts": time.time(),
        "iso": now_utc_iso(),
        "level": level,
        "source": source,
        "message": message,
    }
    if extra:
        event["extra"] = extra

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def new_run_id() -> str:
    return uuid.uuid4().hex[:10]


def snapshot_run(state: Dict[str, Any], run_id: str, note: str = "") -> Path:
    """
    Saves a full snapshot of state into data/runs/<timestamp>_<run_id>.json
    """
    ensure_data_dirs()
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = RUNS_DIR / f"{stamp}_{run_id}.json"
    payload = {
        "run_id": run_id,
        "saved_at": now_utc_iso(),
        "note": note,
        "state": state,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path