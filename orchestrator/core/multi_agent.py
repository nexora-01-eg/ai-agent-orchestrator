"""Multi-Agent Mode: isolated workspaces per agent (git worktree preferred, copy fallback)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class WorkspaceResult:
    agent: str
    workspace: str
    success: bool
    duration: float = 0.0
    files: List[str] = field(default_factory=list)
    tests: str = ""
    errors: List[str] = field(default_factory=list)


class WorkspaceManager:
    def __init__(self, project_root: str | Path):
        self.root = Path(project_root).resolve()

    def base(self, project_path: str) -> Path:
        return Path(project_path).resolve().parent / ".orchestrator" / "workspaces"

    def prepare(self, project_path: str, agent: str) -> Path:
        src = Path(project_path).resolve()
        dest = self.base(str(src)) / agent.lower().replace(" ", "-")
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # try git worktree if src is a clean repo; a dirty tree would make the
        # workspace diverge from the working state (worktree reflects HEAD),
        # so fall back to a working-tree copy in that case.
        try:
            st = subprocess.run(["git", "status", "--porcelain"], cwd=str(src),
                                capture_output=True, text=True, timeout=15)
            dirty = st.returncode != 0 or bool(st.stdout.strip())
        except Exception:
            dirty = True
        if not dirty:
            try:
                br = f"orch/{agent.lower().replace(' ', '-')}"
                subprocess.run(["git", "worktree", "remove", "--force", str(dest)], cwd=str(src),
                               capture_output=True, timeout=20)
                subprocess.run(["git", "branch", "-D", br], cwd=str(src), capture_output=True, timeout=20)
                r = subprocess.run(["git", "worktree", "add", "-b", br, str(dest)], cwd=str(src),
                                   capture_output=True, text=True, timeout=60)
                if r.returncode == 0 and dest.exists():
                    return dest
            except Exception:
                pass
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__",
                                                                 ".venv", "venv", "dist", "build", "target",
                                                                 ".orchestrator"))
        return dest

    def cleanup(self, project_path: str):
        base = self.base(project_path)
        src = Path(project_path).resolve()
        # remove worktrees
        try:
            r = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=str(src),
                               capture_output=True, text=True, timeout=15)
            for line in r.stdout.splitlines():
                if line.startswith("worktree ") and ".orchestrator" in line:
                    subprocess.run(["git", "worktree", "remove", "--force", line.split(" ", 1)[1].strip()],
                                   cwd=str(src), capture_output=True, timeout=30)
        except Exception:
            pass
        shutil.rmtree(base, ignore_errors=True)
