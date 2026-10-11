"""Observability: structured logs per task under logs/YYYY-MM-DD/<task-id>/."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from orchestrator.core.security import SecretScanner


class TaskLogger:
    def __init__(self, project_root: str | Path, task_id: str):
        date = datetime.now().strftime("%Y-%m-%d")
        self.base = Path(project_root) / "logs" / date / task_id
        self.base.mkdir(parents=True, exist_ok=True)
        self.files = {
            "supervisor": self.base / "supervisor.log",
            "agent": self.base / "agent.log",
            "tests": self.base / "tests.log",
            "security": self.base / "security.log",
        }

    def _write(self, key: str, msg: str, redact: bool = True):
        text = SecretScanner.redact_text(msg) if redact else msg
        ts = datetime.now().isoformat()
        with open(self.files[key], "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {text}\n")

    def supervisor(self, msg: str): self._write("supervisor", msg)
    def agent(self, msg: str): self._write("agent", msg)
    def tests(self, msg: str): self._write("tests", msg)
    def security(self, msg: str): self._write("security", msg)

    def write_report(self, report: dict):
        with open(self.base / "report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    @property
    def dir(self) -> Path:
        return self.base
