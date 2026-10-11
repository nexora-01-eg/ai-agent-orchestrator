"""Change Review: git diff summary + unexpected-change detection."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class ChangeReview:
    files_changed: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    diff_stat: str = ""
    warnings: List[str] = field(default_factory=list)
    unexpected: List[str] = field(default_factory=list)


def _git(cwd: Path, *args: str, timeout: int = 15) -> tuple:
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                           text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return r.returncode, r.stdout or "", r.stderr or ""
    except Exception as e:
        return 1, "", str(e)


class ChangeReviewer:
    SENSITIVE_DIRS = ("infra/", "deploy/", ".github/workflows/", "k8s/", "terraform/")
    GENERATED = ("__pycache__/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/",
                 "node_modules/", "dist/", "build/", ".next/", "target/", ".venv/", "venv/")

    def review(self, project_path: str, expected_areas: List[str]) -> ChangeReview:
        p = Path(project_path).resolve()
        rev = ChangeReview()
        rc, out, _ = _git(p, "status", "--porcelain")
        if rc != 0:
            rev.warnings.append("not a git repo or git unavailable; change review limited")
            return rev
        for line in out.strip().splitlines():
            if not line or len(line) < 4:
                continue
            code, f = line[:2], line[3:].strip().strip('"')
            if any(f == g or f.startswith(g) for g in self.GENERATED):
                continue  # ignore bytecode caches / build artifacts
            if code.strip() == "D":
                rev.files_deleted.append(f)
            elif code.strip() == "??":
                rev.files_created.append(f)
            else:
                rev.files_changed.append(f)
        rc2, stat, _ = _git(p, "diff", "--stat")
        if rc2 == 0:
            rev.diff_stat = stat.strip()[:3000]
        # unexpected: many files or sensitive dirs when task is small
        total = len(rev.files_changed) + len(rev.files_created) + len(rev.files_deleted)
        if total > 25:
            rev.warnings.append(f"large change surface: {total} files (review carefully)")
            rev.unexpected = (rev.files_changed + rev.files_created)[:10]
        for f in rev.files_changed + rev.files_created:
            fl = f.lower()
            if fl.startswith(self.SENSITIVE_DIRS) or "dockerfile" in fl or ".env" in fl:
                rev.warnings.append(f"sensitive area touched: {f}")
                rev.unexpected.append(f)
        return rev
