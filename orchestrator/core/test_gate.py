"""Test Gate + smoke validation + build checks."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from orchestrator.core.project_analyzer import ProjectProfile


@dataclass
class GateResult:
    passed: bool
    details: str
    command: str = ""


class TestGate:
    def __init__(self, timeout: int = 180):
        self.timeout = timeout

    def build_if_available(self, project: ProjectProfile) -> Optional[GateResult]:
        p = Path(project.path)
        cmd = None
        if project.language in ("javascript", "typescript") and (p / "package.json").exists():
            try:
                import json
                data = json.loads((p / "package.json").read_text(encoding="utf-8", errors="replace"))
                if "build" in data.get("scripts", {}):
                    cmd = "npm run build"
            except Exception:
                pass
        elif project.language == "rust":
            cmd = "cargo build"
        elif project.language == "go":
            cmd = "go build ./..."
        if not cmd:
            return None
        try:
            r = subprocess.run(cmd, cwd=str(p), shell=True, capture_output=True, text=True,
                               timeout=self.timeout, encoding="utf-8", errors="replace")
            ok = r.returncode == 0
            return GateResult(ok, (r.stdout[-2000:] + r.stderr[-2000:]) if not ok else "build ok", cmd)
        except subprocess.TimeoutExpired:
            return GateResult(False, "build timeout", cmd)
        except Exception as e:
            return GateResult(False, str(e)[:1000], cmd or "")

    def run_tests(self, project: ProjectProfile) -> Optional[GateResult]:
        p = Path(project.path)
        cmd = None
        if project.test_framework == "pytest" or (p / "pytest.ini").exists() or list(p.glob("test_*.py")) or list(p.glob("*_test.py")):
            import sys
            cmd = f'"{sys.executable}" -m pytest -q'
        elif (p / "package.json").exists():
            try:
                import json
                data = json.loads((p / "package.json").read_text(encoding="utf-8", errors="replace"))
                if "test" in data.get("scripts", {}):
                    cmd = "npm test -- --watchAll=false" if "react" in str(data).lower() else "npm test"
            except Exception:
                pass
        elif (p / "Cargo.toml").exists():
            cmd = "cargo test"
        elif (p / "go.mod").exists():
            cmd = "go test ./..."
        if not cmd:
            return None
        try:
            r = subprocess.run(cmd, cwd=str(p), shell=True, capture_output=True, text=True,
                               timeout=self.timeout, encoding="utf-8", errors="replace")
            ok = r.returncode == 0
            out = (r.stdout or "")[-4000:] + ("\n" + (r.stderr or "")[-2000:] if r.stderr else "")
            return GateResult(ok, out or ("tests ok" if ok else "tests failed"), cmd)
        except subprocess.TimeoutExpired:
            return GateResult(False, "tests timeout", cmd)
        except Exception as e:
            return GateResult(False, str(e)[:1000], cmd or "")

    def smoke_validate(self, project_path: str, changed: list) -> GateResult:
        p = Path(project_path)
        if not changed:
            # An execution that changes zero real files did no work:
            # never pass vacuously (agent metadata is already filtered out).
            return GateResult(False, "smoke failed: agent changed no project files")
        missing = [f for f in changed if not (p / f).exists() and not (p / f.lstrip("/\\")).exists()]
        # changed list from git porcelain may include renames; be lenient
        if missing and len(missing) == len(changed):
            return GateResult(False, f"smoke failed: none of the changed files exist: {missing[:3]}")
        return GateResult(True, f"smoke ok: {len(changed)} changed/created file(s) present")
