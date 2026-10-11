"""Agent Capability Matrix with live health checks (no blind trust in agents.json)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from orchestrator.core.config import get_config, PROJECT_ROOT


@dataclass
class AgentHealth:
    name: str
    installed: bool
    executable: str
    authenticated: Optional[bool]  # True/False/None(unknown or N/A)
    model_available: Optional[bool]
    file_access: bool
    shell_access: bool
    network_access: Optional[bool]
    local: bool
    remote: bool
    free: bool
    healthy: bool
    # READY | WARNING | BLOCKED | AUTH_REQUIRED | SERVER_REQUIRED
    # MODEL_REQUIRED | NOT_INSTALLED | ERROR
    status: str
    reason: str
    action: str = ""  # exact manual step when not healthy, "" if none


def _which(cmd: str) -> Optional[str]:
    p = shutil.which(cmd)
    if p:
        return p
    # npm ps1 shims on Windows
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        for cand in (f"{appdata}\\npm\\{cmd}.ps1", f"{appdata}\\npm\\{cmd}.cmd"):
            if cand and os.path.exists(cand):
                return cand
    return None


def _run(cmd: List[str], timeout: int = 15, cwd: str = ".") -> tuple:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=cwd, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "")[:4000], (r.stderr or "")[:4000]
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 127, "", str(e)[:500]


class AgentMatrix:
    """Live health checks for each agent (results cached 60s for dashboards)."""

    _cache: Dict[str, tuple] = {}

    def __init__(self, config=None, project_path: str = "."):
        self.config = config or get_config()
        self.project_path = str(Path(project_path).resolve())

    def check_all(self, use_cache: bool = True) -> Dict[str, AgentHealth]:
        import time as _t
        key = self.project_path
        if use_cache and key in AgentMatrix._cache:
            ts, val = AgentMatrix._cache[key]
            if _t.time() - ts < 60:
                return val
        val = {
            "OpenCode": self.check_opencode(),
            "Aider": self.check_aider(),
            "Gemini": self.check_gemini(),
            "Qwen": self.check_qwen(),
        }
        AgentMatrix._cache[key] = (_t.time(), val)
        return val

    def healthy_agents(self) -> Dict[str, AgentHealth]:
        return {k: v for k, v in self.check_all().items() if v.healthy}

    # ---- individual checks ----
    def _lm_server_state(self) -> str:
        """Probe LM Studio server: 'models' | 'empty' | 'down'.

        /v1/models is the source of truth, never an assumed model name.
        """
        try:
            import requests
            cfg = self.config.config.local_models.lm_studio
            r = requests.get(f"{cfg.url.rstrip('/')}/models",
                             headers={"Authorization": f"Bearer {cfg.api_key}"} if cfg.api_key else {},
                             timeout=6)
            if r.status_code != 200:
                return "down"
            return "models" if r.json().get("data") else "empty"
        except Exception:
            return "down"

    def check_opencode(self) -> AgentHealth:
        exe = _which("opencode")
        if not exe:
            # fallback to configured path
            cfg = self.config.get_agent_config("OpenCode")
            if cfg and cfg.path and os.path.exists(cfg.path):
                exe = cfg.path
        if not exe:
            return AgentHealth("OpenCode", False, "", None, None, False, False, None, True, True, True, False, "NOT_INSTALLED", "opencode executable not found", "install via: npm i -g opencode-ai@latest")
        # opencode works without auth for local/free providers; verify --version
        if exe.endswith(".ps1"):
            rc, _, _ = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", exe, "--version"])
        else:
            rc, _, _ = _run([exe, "--version"])
        ok = rc == 0
        if not ok:
            return AgentHealth(
                "OpenCode", True, exe, None, None, True, True, True, True, True, True,
                False, "ERROR", "opencode --version failed",
                "reinstall via: npm i -g opencode-ai@latest",
            )
        return AgentHealth(
            "OpenCode", True, exe, True, True, True, True, True, True, True, True,
            True, "READY",
            "OpenCode responds to --version; file+shell access verified by design",
            "",
        )

    def check_aider(self) -> AgentHealth:
        exe = _which("aider")
        if not exe:
            return AgentHealth("Aider", False, "", None, None, True, True, None, True, False, True, False, "NOT_INSTALLED", "aider executable not found", "install via: pip install aider-install && aider-install")
        rc, _, _ = _run([exe, "--version"])
        if rc != 0:
            return AgentHealth("Aider", True, exe, True, False, True, True, None, True, False, True, False, "ERROR", "aider --version failed", "reinstall aider")
        # model availability = LM Studio serves a *coding* model (/v1/models is truth).
        # An embedding-only server cannot drive a coding agent: MODEL_REQUIRED, not READY.
        # Single fetch: derive coding list + server state from one response.
        from orchestrator.adapters.lmstudio import LMStudioAdapter
        try:
            lm = LMStudioAdapter(self.config, self.project_path)
            all_models = lm.get_available_models()
            coding = [m for m in all_models if m.get("id", "").lower() and any(
                k in m.get("id", "").lower() for k in ("coder", "code", "qwen", "deepseek", "starcoder", "codellama", "phi", "devstral", "starcode", "opencode"))]
            server_up = True
        except Exception:
            coding, all_models, server_up = [], [], False
        # _lm_server_state distinguishes down vs empty only when fetch failed
        if coding:
            return AgentHealth("Aider", True, exe, True, True, True, True, False, True, False, True, True, "READY", f"aider installed; LM Studio serves coding model(s): {', '.join(m['id'] for m in coding[:3])}", "")
        if not server_up and self._lm_server_state() == "down":
            return AgentHealth("Aider", True, exe, True, False, True, True, False, True, False, True, False, "SERVER_REQUIRED", "LM Studio server is DOWN on localhost:1234", "start LM Studio server: open LM Studio -> Developer tab -> Start Server (or: lms server start --port 1234)")
        detail = "serves zero models" if not all_models else "serves only non-coding models (no coder LLM loaded)"
        return AgentHealth("Aider", True, exe, True, False, True, True, False, True, False, True, False, "MODEL_REQUIRED", f"LM Studio server is UP but {detail}", "in LM Studio: download a coding model (e.g. qwen2.5-coder-7b-instruct, ~4.7GB, needs ~8GB RAM) and load it, then re-run doctor")

    def check_gemini(self) -> AgentHealth:
        exe = _which("gemini")
        if not exe:
            cfg = self.config.get_agent_config("Gemini")
            if cfg and cfg.path and os.path.exists(cfg.path):
                exe = cfg.path
        if not exe:
            return AgentHealth("Gemini", False, "", None, None, True, True, True, False, True, True, False, "NOT_INSTALLED", "gemini executable not found", "install via: npm install -g @google/gemini-cli")
        if exe.endswith(".ps1"):
            rc, _, _ = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", exe, "--version"])
        else:
            rc, _, _ = _run([exe, "--version"])
        if rc != 0:
            return AgentHealth("Gemini", True, exe, None, None, True, True, True, False, True, True, False, "ERROR", "gemini --version failed", "reinstall via: npm install -g @google/gemini-cli")
        # auth check: settings.json or env key (non-interactive, never triggers OAuth)
        authed = self._gemini_authed()
        if authed:
            return AgentHealth("Gemini", True, exe, True, True, True, True, True, False, True, True, True, "READY", "gemini authenticated (settings.json or env key present) - free tier usable", "")
        return AgentHealth("Gemini", True, exe, False, False, True, True, True, False, True, True, False, "AUTH_REQUIRED", "gemini installed but not authenticated (NOT broken)", "run one step: gemini auth  (Google OAuth in browser, free tier)")

    def check_qwen(self) -> AgentHealth:
        exe = _which("qwen")
        if not exe:
            cfg = self.config.get_agent_config("Qwen")
            if cfg and cfg.path and os.path.exists(cfg.path):
                exe = cfg.path
        if not exe:
            return AgentHealth("Qwen", False, "", None, None, True, True, None, True, True, True, False, "NOT_INSTALLED", "qwen executable not found", "install via: npm install -g @qwen-code/qwen-code")
        if exe.endswith(".ps1"):
            rc, _, _ = _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", exe, "--version"])
        else:
            rc, _, _ = _run([exe, "--version"])
        if rc != 0:
            return AgentHealth("Qwen", True, exe, None, None, True, True, None, True, True, True, False, "ERROR", "qwen --version failed", "reinstall via: npm install -g @qwen-code/qwen-code")
        # local-first: LM Studio must serve a *coding* model (embedding-only is not enough).
        # Single fetch: derive coding list + emptiness from one response.
        from orchestrator.adapters.lmstudio import LMStudioAdapter
        try:
            lm = LMStudioAdapter(self.config, self.project_path)
            all_models = lm.get_available_models()
            coding = [m for m in all_models if m.get("id", "").lower() and any(
                k in m.get("id", "").lower() for k in ("coder", "code", "qwen", "deepseek", "starcoder", "codellama", "phi", "devstral", "starcode", "opencode"))]
            server_up = True
        except Exception:
            coding, all_models, server_up = [], [], False
        if coding:
            # Qwen CLI needs ~24K context (n_keep ~23K). Verify the LOADED context
            # via `lms ps`: live-tested that 7B crashes/is unstable at >=24K on
            # 16GB RAM while 4K errors out. No guessing: report what is loaded.
            ctx = self._loaded_context(coding[0]["id"])
            if ctx is not None and ctx < 24000:
                return AgentHealth("Qwen", True, exe, False, False, True, True, False, True, True, True, False, "WARNING", f"coder model loaded at {ctx} ctx; Qwen CLI needs >=24K (unstable on this 16GB box per live tests)", "use Aider/OpenCode for local work, or load the model with larger context if RAM allows")
            return AgentHealth("Qwen", True, exe, True, True, True, True, False, True, True, True, True, "READY", f"qwen can use local endpoint --auth-type openai (coding model: {coding[0]['id']})", "")
        if not server_up and self._lm_server_state() == "down":
            return AgentHealth("Qwen", True, exe, False, False, True, True, None, True, True, True, False, "SERVER_REQUIRED", "LM Studio server DOWN; cloud --auth-type not configured", "start LM Studio server (Developer tab -> Start Server, or: lms server start --port 1234), then load a coding model")
        detail = "serves zero models" if not all_models else "serves only non-coding models (no coder LLM loaded)"
        return AgentHealth("Qwen", True, exe, False, False, True, True, False, True, True, True, False, "MODEL_REQUIRED", f"LM Studio server is UP but {detail}; cloud auth not configured", "in LM Studio: download + load a coding model (e.g. qwen2.5-coder-7b-instruct), then re-run doctor")

    def _loaded_context(self, model_id: str) -> Optional[int]:
        """Read loaded context length from `lms ps` (live, no guessing)."""
        try:
            import re as _re
            lms = shutil.which("lms")
            if not lms:
                return None
            rc, out, _ = _run([lms, "ps"], timeout=20)
            if rc != 0:
                return None
            for line in out.splitlines():
                if model_id.lower() in line.lower():
                    m = _re.search(r"\b(\d{4,6})\b", line)
                    # CONTEXT column: take the first 4-6 digit number that looks like ctx
                    if m:
                        for tok in _re.findall(r"\b\d{4,6}\b", line):
                            v = int(tok)
                            if 2048 <= v <= 1000000 and v != 4680:  # skip SIZE like 4.68 GB artifacts
                                return v
            return None
        except Exception:
            return None

    # ---- helpers ----
    def _gemini_authed(self) -> bool:
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return True
        home = Path.home()
        for cand in (home / ".gemini" / "settings.json", home / ".config" / "gemini" / "settings.json"):
            try:
                if cand.exists() and cand.stat().st_size > 10:
                    return True
            except Exception:
                continue
        return False

    def to_dict(self) -> Dict[str, dict]:
        return {k: asdict(v) for k, v in self.check_all().items()}
