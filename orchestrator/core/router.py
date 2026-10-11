"""Smart Router - descriptive reasoning only, no score display."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from orchestrator.core.agent_matrix import AgentHealth
from orchestrator.core.model_discovery import ModelInfo
from orchestrator.core.project_analyzer import ProjectProfile
from orchestrator.core.task_planner import TaskProfile


@dataclass
class Route:
    agent: str
    model: str
    execution_mode: str  # local | remote-free
    reason: str


class SmartRouter:
    """Capability-based routing with free/local enforcement."""

    def __init__(self, config=None):
        from orchestrator.core.config import get_config
        self.config = config or get_config()

    def route(self, project: ProjectProfile, task: TaskProfile,
              health: Dict[str, AgentHealth], models: List[ModelInfo],
              user_agent: Optional[str] = None, user_model: Optional[str] = None) -> Optional[Route]:
        cfg = self.config.config
        free_only = cfg.general.free_only
        local_first = cfg.general.local_first

        healthy = {k: v for k, v in health.items() if v.healthy}
        if user_agent:
            h = healthy.get(user_agent)
            if not h:
                return None
            model = self._pick_model(user_agent, user_model, models, task, local_first)
            if model is None and self._needs_model(user_agent):
                return None
            mode = "local" if self._is_local_model(model, models) or (h.local and not h.remote) else "remote-free"
            return Route(user_agent, model or "", mode, f"you selected {user_agent}; it is healthy and allowed")

        local_models = [m for m in models if m.coding]
        has_local = len(local_models) > 0  # coder LLMs only; embedding servers don't count

        # local/private tasks -> local agent
        if local_first and has_local and not task.network_required:
            for cand in ("OpenCode", "Aider", "Qwen"):
                h = healthy.get(cand)
                if h and h.local:
                    m = self._pick_model(cand, user_model, models, task, True)
                    if m:
                        why = {
                            "OpenCode": "large multi-file work runs well with OpenCode on a local model",
                            "Aider": "git-heavy change fits Aider's git-native workflow on a local model",
                            "Qwen": "complex orchestration fits Qwen with a local model",
                        }[cand]
                        # git-heavy override to Aider
                        if task.affected_areas and "git" in " ".join(task.affected_areas).lower() and "Aider" in healthy:
                            hm = self._pick_model("Aider", user_model, models, task, True)
                            if hm:
                                return Route("Aider", hm, "local", "git-heavy task fits Aider's git-native workflow on a local model")
                        return Route(cand, m, "local", why)

        # research/network tasks -> remote-free agent that is healthy
        if task.network_required:
            if "Gemini" in healthy:
                return Route("Gemini", user_model or "", "remote-free", "task needs internet research and Gemini is authenticated with a free tier")

        # git-heavy with any healthy (even without local)
        if "Aider" in healthy:
            # Aider is preferred for git-heavy even remote-free? Aider supports local best; still allow
            pass

        # fallback: first healthy respecting free_only + required capabilities
        order = ["OpenCode", "Aider", "Qwen", "Gemini"]
        for cand in order:
            h = healthy.get(cand)
            if not h:
                continue
            if free_only and not h.free:
                continue
            if task.network_required and not h.network_access:
                continue  # research task needs a network-capable agent
            m = self._pick_model(cand, user_model, models, task, local_first)
            if m is None and self._needs_model(cand):
                continue
            mode = "local" if (m and self._is_local_model(m, models)) else ("local" if (h.local and has_local and not task.network_required) else "remote-free")
            why = {
                "OpenCode": "OpenCode is healthy and fits general coding work",
                "Aider": "Aider is healthy and fits git-scoped work",
                "Qwen": "Qwen is healthy and fits this task",
                "Gemini": "Gemini is healthy and authenticated with a free tier",
            }[cand]
            return Route(cand, m or "", mode, why)
        return None

    def _needs_model(self, agent: str) -> bool:
        # OpenCode/Aider/Qwen need a model name when using local endpoint; Gemini uses its own
        return agent in ("Aider", "Qwen", "OpenCode")

    def _is_local_model(self, model: str, models: List[ModelInfo]) -> bool:
        ids = {m.id for m in models}
        return bool(model) and model in ids

    def _pick_model(self, agent: str, user_model: Optional[str], models: List[ModelInfo],
                    task: TaskProfile, local_first: bool) -> Optional[str]:
        if user_model:
            return user_model
        if agent == "Gemini":
            return ""  # provider-managed
        coding_only = [m for m in models if m.coding]
        if not coding_only:
            # No coder LLM available locally: Aider/Qwen cannot run;
            # OpenCode falls back to its built-in free provider (never an embedding model).
            return "" if agent == "OpenCode" else None
        # prefer coding models
        coding = coding_only
        # simple preference
        for kw in ("qwen", "deepseek", "devstral", "starcoder", "codellama", "phi", "code"):
            for m in coding:
                if kw in m.id.lower():
                    return m.id
        return coding[0].id
