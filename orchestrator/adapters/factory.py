"""Agent Adapter Factory"""

from typing import Dict, Type, Optional, List
from orchestrator.adapters.base import BaseAgentAdapter
from orchestrator.adapters.opencode import OpenCodeAdapter
from orchestrator.adapters.aider import AiderAdapter
from orchestrator.adapters.gemini import GeminiAdapter
from orchestrator.adapters.qwen import QwenAdapter
from orchestrator.adapters.lmstudio import LMStudioAdapter
from orchestrator.core.config import get_config


class AdapterFactory:
    """Factory for creating agent adapters"""

    _adapters: Dict[str, Type[BaseAgentAdapter]] = {
        'OpenCode': OpenCodeAdapter,
        'Aider': AiderAdapter,
        'Gemini': GeminiAdapter,
        'Qwen': QwenAdapter,
        'LM Studio': LMStudioAdapter,
    }

    def __init__(self, config=None):
        self.config = config or get_config()

    def get_available_adapters(self, project_path: str) -> Dict[str, BaseAgentAdapter]:
        """Get all available and working adapters"""
        adapters = {}
        working_agents = self.config.get_working_agents()

        for name in working_agents:
            adapter = self.create_adapter(name, project_path)
            if adapter and adapter.check_available():
                adapters[name] = adapter

        return adapters

    def get_all_adapters(self, project_path: str) -> Dict[str, BaseAgentAdapter]:
        """Get all adapters (including non-working ones)"""
        adapters = {}
        enabled_agents = self.config.get_enabled_agents()

        for name in enabled_agents:
            adapter = self.create_adapter(name, project_path)
            if adapter:
                adapters[name] = adapter

        return adapters

    def register_adapter(self, name: str, adapter_class: Type[BaseAgentAdapter]):
        """Register a new adapter type"""
        self._adapters[name] = adapter_class

    def get_adapter_names(self) -> List[str]:
        """Get list of registered adapter names"""
        self._autoload_plugins()
        return list(self._adapters.keys())

    def _autoload_plugins(self):
        """Auto-discover orchestrator/agents/*.py plugins (no core changes needed)."""
        try:
            from orchestrator.agents.loader import discover_plugins
            for name, cls in discover_plugins().items():
                if name not in self._adapters:
                    self._adapters[name] = cls
        except Exception:
            pass

    def create_adapter(self, agent_name: str, project_path: str) -> Optional[BaseAgentAdapter]:
        """Create an adapter instance for the given agent (with plugin autoload)."""
        self._autoload_plugins()
        adapter_class = self._adapters.get(agent_name)
        if not adapter_class:
            return None
        try:
            return adapter_class(self.config, project_path)
        except Exception as e:
            print(f"Error creating adapter for {agent_name}: {e}")
            return None