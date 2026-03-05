from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Dict, List, Optional

from backend.core.persistence import append_log as persist_append_log
from backend.core.persistence import load_state, save_state, ensure_data_dirs

# ----------------------------
# Data models
# ----------------------------

@dataclass
class AgentState:
    name: str
    role: str
    status: str  # idle / working / blocked
    current_task_id: Optional[str] = None
    last_action: Optional[str] = None


@dataclass
class TaskState:
    id: str
    title: str
    status: str  # pending / in_progress / completed / failed / rejected
    assigned_agent: str
    result: Optional[str] = None


@dataclass
class LogEvent:
    ts: float
    level: str
    source: str
    message: str


_lock = Lock()

_agents: Dict[str, AgentState] = {
    "manager": AgentState("manager", "Manager", "idle"),
    "dev_1": AgentState("dev_1", "Developer", "idle"),
    "qa_1": AgentState("qa_1", "Tester", "idle"),
    "devops": AgentState("devops", "DevOps", "idle"),
    "reviewer": AgentState("reviewer", "Reviewer", "idle"),
}

_tasks: Dict[str, TaskState] = {}
_logs: List[LogEvent] = []
_run_in_progress: bool = False


# ----------------------------
# Persistence helpers
# ----------------------------

def snapshot_state() -> dict:
    with _lock:
        return {
            "run_in_progress": _run_in_progress,
            "agents": [asdict(a) for a in _agents.values()],
            "tasks": [asdict(t) for t in _tasks.values()],
        }


def persist_state() -> None:
    """
    Save the current state to data/state.json (agents/tasks/run flag).
    """
    save_state(snapshot_state())


def apply_state(state: dict) -> None:
    """
    Restore agents/tasks/run_in_progress from a dict (from data/state.json).
    Logs are not restored from JSONL into memory (we keep memory logs session-only).
    """
    global _run_in_progress
    with _lock:
        _run_in_progress = bool(state.get("run_in_progress", False))

        # Agents
        agents_list = state.get("agents", [])
        if isinstance(agents_list, list):
            for a in agents_list:
                name = a.get("name")
                if name and name in _agents:
                    _agents[name].status = a.get("status", _agents[name].status)
                    _agents[name].current_task_id = a.get("current_task_id")
                    _agents[name].last_action = a.get("last_action")

        # Tasks
        _tasks.clear()
        tasks_list = state.get("tasks", [])
        if isinstance(tasks_list, list):
            for t in tasks_list:
                try:
                    task = TaskState(
                        id=t["id"],
                        title=t["title"],
                        status=t["status"],
                        assigned_agent=t["assigned_agent"],
                        result=t.get("result"),
                    )
                    _tasks[task.id] = task
                except Exception:
                    # ignore broken task records
                    continue


def boot_restore_state() -> None:
    """
    Call once on program start.
    """
    ensure_data_dirs()
    saved = load_state()
    if saved:
        apply_state(saved)
        add_log("INFO", "orchestrator", "Restored state from data/state.json")
    else:
        add_log("INFO", "orchestrator", "No saved state found. Starting fresh.")
    persist_state()


# ----------------------------
# Public API used by orchestrator/routes
# ----------------------------

def add_log(level: str, source: str, message: str) -> None:
    event = LogEvent(time.time(), level, source, message)
    with _lock:
        _logs.append(event)
    # persist log line to JSONL
    persist_append_log(level, source, message)


def get_run_in_progress() -> bool:
    with _lock:
        return _run_in_progress


def set_run_in_progress(value: bool) -> None:
    global _run_in_progress
    with _lock:
        _run_in_progress = value
    persist_state()


def upsert_task(task: TaskState) -> None:
    with _lock:
        _tasks[task.id] = task
    persist_state()


def update_task(task_id: str, **kwargs) -> None:
    with _lock:
        t = _tasks[task_id]
        for k, v in kwargs.items():
            setattr(t, k, v)
    persist_state()


def update_agent(agent_key: str, **kwargs) -> None:
    with _lock:
        a = _agents[agent_key]
        for k, v in kwargs.items():
            setattr(a, k, v)
    persist_state()


def snapshot_for_api(include_logs: bool = True) -> dict:
    """
    Returns state for /api/state. Includes last 250 in-memory logs for UI.
    """
    with _lock:
        payload = {
            "run_in_progress": _run_in_progress,
            "agents": [asdict(a) for a in _agents.values()],
            "tasks": [asdict(t) for t in _tasks.values()],
        }
        if include_logs:
            payload["logs"] = [asdict(e) for e in _logs[-250:]]
        return payload


def reset_state() -> None:
    global _run_in_progress
    with _lock:
        _tasks.clear()
        _logs.clear()
        for a in _agents.values():
            a.status = "idle"
            a.current_task_id = None
            a.last_action = None
        _run_in_progress = False

    add_log("INFO", "orchestrator", "State reset.")
    persist_state()