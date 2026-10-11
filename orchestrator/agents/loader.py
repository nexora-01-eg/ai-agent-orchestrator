"""Plugin loader for orchestrator/agents/*.py.

Convention: plugin module defines ADAPTER_NAME (str) and ADAPTER_CLASS
(a BaseAgentAdapter subclass). Example agents/myagent.py:

    from orchestrator.adapters.base import BaseAgentAdapter, ...
    ADAPTER_NAME = "MyAgent"
    class MyAgentAdapter(BaseAgentAdapter): ...
    ADAPTER_CLASS = MyAgentAdapter
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Dict, Type

from orchestrator.adapters.base import BaseAgentAdapter


def discover_plugins() -> Dict[str, Type[BaseAgentAdapter]]:
    out: Dict[str, Type[BaseAgentAdapter]] = {}
    d = Path(__file__).parent
    for f in sorted(d.glob("*.py")):
        if f.name in ("__init__.py", "loader.py"):
            continue
        mod_name = f"orchestrator.agents.{f.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, str(f))
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            name = getattr(mod, "ADAPTER_NAME", None)
            cls = getattr(mod, "ADAPTER_CLASS", None)
            if isinstance(name, str) and isinstance(cls, type) and issubclass(cls, BaseAgentAdapter):
                out[name] = cls
        except Exception as e:
            print(f"Plugin load skipped {f.name}: {e}")
    return out
