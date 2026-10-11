"""LocalDecisionEngineAdapter — optional decision accelerator (opt-in, off by default).

Does NOT replace SmartRouter or any adapter. When disabled (default) every
method returns {"status": "disabled"} and callers keep existing logic.
Enable only after benchmarking on your own tasks:

    gate = LocalDecisionEngineAdapter(enabled=True)
    hint = gate.route_hint("Refactor the rendering module across 40 files")

Needs the local-decision-engine package importable: set
LOCAL_DECISION_ENGINE_ROOT=C:\\Users\\NOUR SOFT\\Documents\\Default Project\\local-decision-engine
or run with its .venv / src on PYTHONPATH. If unavailable, the adapter
reports status="unavailable" and callers fall back to existing logic.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

_ENGINE = None
_ENGINE_ERROR = ""


def _load():
    global _ENGINE, _ENGINE_ERROR
    if _ENGINE is not None or _ENGINE_ERROR:
        return
    try:
        from decision_engine.adapters.orchestrator import (  # type: ignore
            LocalDecisionEngineAdapter as A)
        _ENGINE = A
    except ImportError as exc:
        root = os.environ.get("LOCAL_DECISION_ENGINE_ROOT", "")
        src = os.path.join(root, "src") if root else ""
        if src and os.path.isdir(src) and src not in sys.path:
            sys.path.insert(0, src)
            try:
                from decision_engine.adapters.orchestrator import (  # type: ignore
                    LocalDecisionEngineAdapter as A)
                _ENGINE = A
                return
            except ImportError as exc2:
                exc = exc2
        _ENGINE_ERROR = str(exc)[:200]


class LocalDecisionEngineAdapter:
    """Thin, safe wrapper. All methods degrade to disabled/unavailable."""

    def __init__(self, enabled: bool = False, threshold: float = 0.6):
        _load()
        self.enabled = enabled
        self.threshold = threshold
        self._inner = _ENGINE(threshold=threshold,
                              enabled=enabled) if _ENGINE else None

    @property
    def available(self) -> bool:
        return self._inner is not None

    def _off(self, why: str) -> Dict[str, Any]:
        return {"status": why, "hint": None}

    def route_hint(self, task: str) -> Dict[str, Any]:
        if self._inner is None:
            return self._off("unavailable:" + _ENGINE_ERROR)
        return self._inner.route_hint(task)

    def classify_task(self, task: str) -> Dict[str, Any]:
        if self._inner is None:
            return self._off("unavailable:" + _ENGINE_ERROR)
        return self._inner.classify_task(task)

    def decide_retry(self, agent_output: str, exit_code: int = 0) -> Dict[str, Any]:
        if self._inner is None:
            return self._off("unavailable:" + _ENGINE_ERROR)
        return self._inner.decide_retry(agent_output, exit_code)

    def decide_fallback(self, error: str) -> Dict[str, Any]:
        if self._inner is None:
            return self._off("unavailable:" + _ENGINE_ERROR)
        return self._inner.decide_fallback(error)

    def needs_large_llm(self, task: str) -> Dict[str, Any]:
        if self._inner is None:
            return self._off("unavailable:" + _ENGINE_ERROR)
        return self._inner.needs_large_llm(task)

    def needs_review(self, agent_result: str) -> Dict[str, Any]:
        if self._inner is None:
            return self._off("unavailable:" + _ENGINE_ERROR)
        return self._inner.needs_review(agent_result)
