from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import get_settings


@dataclass
class AgentTrace:
    trace_id: str
    started_at: float = field(default_factory=time.perf_counter)
    events: list[dict[str, Any]] = field(default_factory=list)

    def add(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append(
            {
                "type": event_type,
                "at_ms": round((time.perf_counter() - self.started_at) * 1000, 2),
                "payload": payload or {},
            }
        )

    @property
    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        return {"trace_id": self.trace_id, "events": self.events, "elapsed_ms": self.elapsed_ms}


class TraceStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().logs_dir
        self.path.mkdir(parents=True, exist_ok=True)

    def save(self, trace: AgentTrace) -> None:
        target = self.path / f"{trace.trace_id}.json"
        target.write_text(json.dumps(trace.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, trace_id: str) -> dict[str, Any] | None:
        target = self.path / f"{trace_id}.json"
        if not target.exists():
            return None
        return json.loads(target.read_text(encoding="utf-8"))
