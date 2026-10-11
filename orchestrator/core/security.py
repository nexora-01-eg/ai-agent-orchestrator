"""Security Gate: secret scanning + redaction + remote-send gate."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_SECRET_PATTERNS = [
    r"\.env$",
    r"\.env\..*",
    r".*\.pem$",
    r".*\.key$",
    r".*\.p12$",
    r".*\.pfx$",
    r"(^|[\\/])id_rsa$",
    r"(^|[\\/])id_ed25519$",
    r"credentials\.json$",
    r"secrets\.json$",
    r".*secret.*",
    r".*password.*",
    r".*passwd.*",
    r".*token.*",
    r"api[_-]?key.*",
    r".*auth.*\.json$",
]

CONTENT_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)(['\"]?)([A-Za-z0-9_\-]{8,})(['\"]?)"), r"\1\2***REDACTED***\4"),
    (re.compile(r"(?i)(secret\s*[:=]\s*)(['\"]?)([^\s'\"]{6,})(['\"]?)"), r"\1\2***REDACTED***\4"),
    (re.compile(r"(?i)(password\s*[:=]\s*)(['\"]?)([^\s'\"]{4,})(['\"]?)"), r"\1\2***REDACTED***\4"),
    (re.compile(r"(?i)(bearer\s+)([A-Za-z0-9_\-\.~+/=]{8,})"), r"\1***REDACTED***"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]{0,200}?-----END"), "-----BEGIN ***REDACTED*** PRIVATE KEY-----"),
    (re.compile(r"(?i)(sk-[A-Za-z0-9]{8,})"), "***REDACTED***"),
    (re.compile(r"(?i)(ghp_[A-Za-z0-9]{8,})"), "***REDACTED***"),
    (re.compile(r"(?i)(gho_[A-Za-z0-9]{8,})"), "***REDACTED***"),
]


@dataclass
class SecretScanResult:
    blocked_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    allowed: bool = True


class SecretScanner:
    def __init__(self, patterns: List[str] | None = None, exclude: List[str] | None = None):
        self.patterns = [re.compile(p, re.I) for p in (patterns or DEFAULT_SECRET_PATTERNS)]
        self.exclude = [re.compile(p, re.I) for p in (exclude or [r".*\.example$", r".*\.template$", r".*\.sample$"])]

    def is_excluded(self, rel: str) -> bool:
        return any(p.search(rel) for p in self.exclude)

    def matches(self, rel: str) -> bool:
        if self.is_excluded(rel):
            return False
        return any(p.search(rel) for p in self.patterns)

    def scan_paths(self, rel_paths: List[str]) -> SecretScanResult:
        blocked = [p for p in rel_paths if self.matches(p)]
        return SecretScanResult(blocked_files=blocked, allowed=len(blocked) == 0,
                                warnings=[f"secret-like file would be sent to remote agent: {b}" for b in blocked])

    def scan_project(self, project_path: str) -> SecretScanResult:
        root = Path(project_path).resolve()
        rels: List[str] = []
        skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "target"}
        try:
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if any(part in skip for part in p.parts):
                    continue
                try:
                    rel = str(p.relative_to(root)).replace("\\", "/")
                except Exception:
                    continue
                if self.matches(rel):
                    rels.append(rel)
        except Exception:
            pass
        return SecretScanResult(blocked_files=rels, allowed=True,
                                warnings=[f"secret-like file present in project (will NOT be sent): {b}" for b in rels])

    @staticmethod
    def redact_text(text: str) -> str:
        out = text or ""
        for rx, repl in CONTENT_PATTERNS:
            out = rx.sub(repl, out)
        return out


def remote_send_gate(agent: str, is_local: bool, changed_or_context_files: List[str],
                     scanner: SecretScanner) -> Tuple[bool, List[str]]:
    """Decide whether files may be sent to a remote agent. Local execution always allowed."""
    if is_local:
        return True, []
    res = scanner.scan_paths(changed_or_context_files or [])
    if res.blocked_files:
        return False, res.warnings
    return True, []
