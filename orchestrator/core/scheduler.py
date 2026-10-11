"""Optional scheduler: stored tasks only, never auto-runs without explicit command."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ScheduledTask:
    id: str
    project: str
    task: str
    agent_policy: str = "auto"
    model_policy: str = "auto"
    mode: str = "AUTO"
    schedule: str = "once"  # once | hourly | daily
    created_at: str = ""
    last_run: str = ""
    enabled: bool = True


class Scheduler:
    def __init__(self, project_root: str | Path):
        self.path = Path(project_root) / "scheduler.json"
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _load(self) -> List[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except Exception:
            return []

    def _save(self, items: List[dict]):
        self.path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def add(self, project: str, task: str, agent_policy: str = "auto",
            model_policy: str = "auto", mode: str = "AUTO", schedule: str = "once") -> ScheduledTask:
        st = ScheduledTask(id=uuid.uuid4().hex[:8], project=project, task=task,
                           agent_policy=agent_policy, model_policy=model_policy,
                           mode=mode, schedule=schedule, created_at=datetime.now().isoformat())
        items = self._load()
        items.append(asdict(st))
        self._save(items)
        return st

    def list(self) -> List[dict]:
        return self._load()

    def remove(self, task_id: str) -> bool:
        items = self._load()
        new = [x for x in items if x.get("id") != task_id]
        self._save(new)
        return len(new) != len(items)

    def mark_run(self, task_id: str):
        items = self._load()
        for x in items:
            if x.get("id") == task_id:
                x["last_run"] = datetime.now().isoformat()
        self._save(items)
