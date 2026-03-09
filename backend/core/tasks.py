from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class PlannedTask:
    title: str
    task_type: str
    assigned_agent: str
    payload: Dict[str, Any] = field(default_factory=dict)