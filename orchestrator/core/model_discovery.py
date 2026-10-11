"""Model Discovery - query LM Studio / Ollama, never invent model names."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests


@dataclass
class ModelInfo:
    id: str
    owned_by: str = "unknown"
    context_length: Optional[int] = None
    available: bool = True
    source: str = "lm-studio"
    coding: bool = False


_CODING_KW = ("coder", "code", "qwen", "deepseek", "starcoder", "codellama", "phi", "devstral", "starcode", "opencode")


class ModelDiscovery:
    def __init__(self, config=None, timeout: int = 8):
        from orchestrator.core.config import get_config
        self.config = config or get_config()
        self.timeout = timeout
        self._cache: Dict[str, tuple] = {}

    def discover(self, force: bool = False) -> Dict[str, List[ModelInfo]]:
        return {
            "lm-studio": self.lm_studio_models(force=force),
            "ollama": self.ollama_models(force=force),
        }

    def lm_studio_models(self, force: bool = False) -> List[ModelInfo]:
        cfg = self.config.config.local_models.lm_studio
        return self._fetch_openai_compatible(cfg.url, cfg.api_key, "lm-studio", force)

    def ollama_models(self, force: bool = False) -> List[ModelInfo]:
        cfg = self.config.config.local_models.ollama
        return self._fetch_openai_compatible(cfg.url, cfg.api_key, "ollama", force)

    def all_coding_models(self) -> List[ModelInfo]:
        out = []
        for m in self.lm_studio_models() + self.ollama_models():
            if m.coding:
                out.append(m)
        return out

    def best_coding_model(self) -> Optional[ModelInfo]:
        coding = self.all_coding_models()
        if not coding:
            return None
        pref = ("qwen", "deepseek", "devstral", "starcoder", "codellama", "phi", "code")
        def score(m: ModelInfo) -> int:
            mid = m.id.lower()
            for i, p in enumerate(pref):
                if p in mid:
                    return 100 - i
            return 0
        return sorted(coding, key=score, reverse=True)[0]

    def _fetch_openai_compatible(self, base_url: str, api_key: str, source: str, force: bool) -> List[ModelInfo]:
        now = time.time()
        if not force and source in self._cache and now - self._cache[source][0] < 30:
            return self._cache[source][1]
        out: List[ModelInfo] = []
        try:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            r = requests.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=self.timeout)
            if r.status_code != 200:
                self._cache[source] = (now, [])
                return []
            for m in r.json().get("data", []):
                mid = m.get("id", "unknown")
                ctx = None
                meta = m.get("meta") or {}
                for k in ("n_ctx", "context_length", "num_ctx", "max_context_length"):
                    if isinstance(meta.get(k), int):
                        ctx = meta[k]
                        break
                coding = any(k in mid.lower() for k in _CODING_KW)
                out.append(ModelInfo(id=mid, owned_by=m.get("owned_by", "unknown"),
                                     context_length=ctx, available=True, source=source, coding=coding))
        except Exception:
            out = []
        self._cache[source] = (now, out)
        return out
