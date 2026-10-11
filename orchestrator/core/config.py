"""Configuration Management"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


@dataclass
class AgentConfig:
    name: str
    command: str
    version: str = ""
    path: str = ""
    enabled: bool = True
    args: list = field(default_factory=list)
    env: dict = field(default_factory=dict)
    supports_local: bool = False
    local_model_config: dict = field(default_factory=dict)
    requires_auth: bool = False
    free_tier: bool = True
    license: str = ""


@dataclass
class LocalModelServer:
    name: str
    enabled: bool
    url: str
    api_key: str = ""
    models: list = field(default_factory=list)


@dataclass
class GeneralConfig:
    workspace_dir: str
    log_level: str = "INFO"
    max_retries: int = 3
    default_timeout: int = 300
    auto_approve: bool = False
    confirm_destructive: bool = True
    free_only: bool = True
    local_first: bool = True


@dataclass
class AgentPreferences:
    default_agent: str = "auto"
    fallback_agents: list = field(default_factory=list)
    prefer_local_models: bool = True


@dataclass
class LocalModelsConfig:
    lm_studio: LocalModelServer
    ollama: LocalModelServer


@dataclass
class ExecutionConfig:
    create_git_checkpoint: bool = True
    backup_before_changes: bool = True
    max_file_size_mb: int = 10
    excluded_dirs: list = field(default_factory=list)
    excluded_files: list = field(default_factory=list)


@dataclass
class TestingConfig:
    auto_detect: bool = True
    run_after_changes: bool = True
    commands: dict = field(default_factory=dict)


@dataclass
class SafetyConfig:
    blocked_commands: list = field(default_factory=list)
    blocked_paths: list = field(default_factory=list)
    require_confirmation_for: list = field(default_factory=list)


@dataclass
class HistoryConfig:
    enabled: bool = True
    db_path: str = ""
    max_entries: int = 1000


@dataclass
class DashboardConfig:
    enabled: bool = False
    port: int = 8787
    host: str = "127.0.0.1"


@dataclass
class SupervisorConfig:
    task_modes: list = field(default_factory=lambda: ["SAFE", "AUTO", "AUTONOMOUS"])
    default_mode: str = "AUTO"
    cost_policy: str = "ZERO_COST"
    max_attempts: int = 3


@dataclass
class SchedulerConfig:
    enabled: bool = True


@dataclass
class SecretScannerConfig:
    enabled: bool = True
    patterns: list = field(default_factory=list)
    exclude_patterns: list = field(default_factory=list)


@dataclass
class OrchestratorConfig:
    general: GeneralConfig
    agent_preferences: AgentPreferences
    local_models: LocalModelsConfig
    agents: Dict[str, AgentConfig]
    execution: ExecutionConfig
    testing: TestingConfig
    safety: SafetyConfig
    history: HistoryConfig
    dashboard: DashboardConfig
    supervisor: SupervisorConfig = field(default_factory=SupervisorConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    secret_scanner: SecretScannerConfig = field(default_factory=SecretScannerConfig)


class ConfigManager:
    """Manages configuration loading and validation"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or str(PROJECT_ROOT / "config.yaml")
        self._config: Optional[OrchestratorConfig] = None

    @property
    def config(self) -> OrchestratorConfig:
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> OrchestratorConfig:
        """Load configuration from YAML file"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Parse general config
        general_data = data.get('general', {})
        general = GeneralConfig(
            workspace_dir=general_data.get('workspace_dir', str(PROJECT_ROOT / 'workspaces')),
            log_level=general_data.get('log_level', 'INFO'),
            max_retries=general_data.get('max_retries', 3),
            default_timeout=general_data.get('default_timeout', 300),
            auto_approve=general_data.get('auto_approve', False),
            confirm_destructive=general_data.get('confirm_destructive', True),
            free_only=general_data.get('free_only', True),
            local_first=general_data.get('local_first', True)
        )

        # Parse agent preferences
        agent_prefs_data = data.get('agent_preferences', {})
        agent_preferences = AgentPreferences(
            default_agent=agent_prefs_data.get('default_agent', 'auto'),
            fallback_agents=agent_prefs_data.get('fallback_agents', []),
            prefer_local_models=agent_prefs_data.get('prefer_local_models', True)
        )

        # Parse local models
        local_models_data = data.get('local_models', {})
        lm_studio_data = local_models_data.get('lm_studio', {})
        ollama_data = local_models_data.get('ollama', {})
        local_models = LocalModelsConfig(
            lm_studio=LocalModelServer(
                name="LM Studio",
                enabled=lm_studio_data.get('enabled', True),
                url=lm_studio_data.get('url', 'http://localhost:1234/v1'),
                api_key=lm_studio_data.get('api_key', 'lm-studio')
            ),
            ollama=LocalModelServer(
                name="Ollama",
                enabled=ollama_data.get('enabled', False),
                url=ollama_data.get('url', 'http://localhost:11434/v1'),
                api_key=ollama_data.get('api_key', '')
            )
        )

        # Parse agents
        agents = {}
        agents_data = data.get('agents', {})
        for name, agent_data in agents_data.items():
            agents[name] = AgentConfig(
                name=name,
                command=agent_data.get('command', name.lower()),
                version=agent_data.get('version', ''),
                path=agent_data.get('path', ''),
                enabled=agent_data.get('enabled', True),
                args=agent_data.get('args', []),
                env=agent_data.get('env', {}),
                supports_local=agent_data.get('supports_local', False),
                local_model_config=agent_data.get('local_model_config', {}),
                requires_auth=agent_data.get('requires_auth', False),
                free_tier=agent_data.get('free_tier', True),
                license=agent_data.get('license', '')
            )

        # Parse execution config
        execution_data = data.get('execution', {})
        execution = ExecutionConfig(
            create_git_checkpoint=execution_data.get('create_git_checkpoint', True),
            backup_before_changes=execution_data.get('backup_before_changes', True),
            max_file_size_mb=execution_data.get('max_file_size_mb', 10),
            excluded_dirs=execution_data.get('excluded_dirs', []),
            excluded_files=execution_data.get('excluded_files', [])
        )

        # Parse testing config
        testing_data = data.get('testing', {})
        testing = TestingConfig(
            auto_detect=testing_data.get('auto_detect', True),
            run_after_changes=testing_data.get('run_after_changes', True),
            commands=testing_data.get('commands', {})
        )

        # Parse safety config
        safety_data = data.get('safety', {})
        safety = SafetyConfig(
            blocked_commands=safety_data.get('blocked_commands', []),
            blocked_paths=safety_data.get('blocked_paths', []),
            require_confirmation_for=safety_data.get('require_confirmation_for', [])
        )

        # Parse history config
        history_data = data.get('history', {})
        history = HistoryConfig(
            enabled=history_data.get('enabled', True),
            db_path=history_data.get('db_path', str(PROJECT_ROOT / 'orchestrator.db')),
            max_entries=history_data.get('max_entries', 1000)
        )

        # Parse dashboard config
        dashboard_data = data.get('dashboard', {})
        dashboard = DashboardConfig(
            enabled=dashboard_data.get('enabled', False),
            port=dashboard_data.get('port', 8787),
            host=dashboard_data.get('host', '127.0.0.1')
        )

        # Parse supervisor config
        sup_data = data.get('supervisor', {})
        supervisor = SupervisorConfig(
            task_modes=sup_data.get('task_modes', ["SAFE", "AUTO", "AUTONOMOUS"]),
            default_mode=sup_data.get('default_mode', 'AUTO'),
            cost_policy=sup_data.get('cost_policy', 'ZERO_COST'),
            max_attempts=sup_data.get('max_attempts', 3),
        )

        # Parse scheduler config
        sched_data = data.get('scheduler', {})
        scheduler = SchedulerConfig(
            enabled=sched_data.get('enabled', True),
        )

        # Parse secret scanner config
        sec_data = data.get('secret_scanner', {})
        secret_scanner = SecretScannerConfig(
            enabled=sec_data.get('enabled', True),
            patterns=sec_data.get('patterns', []),
            exclude_patterns=sec_data.get('exclude_patterns', []),
        )

        return OrchestratorConfig(
            general=general,
            agent_preferences=agent_preferences,
            local_models=local_models,
            agents=agents,
            execution=execution,
            testing=testing,
            safety=safety,
            history=history,
            dashboard=dashboard,
            supervisor=supervisor,
            scheduler=scheduler,
            secret_scanner=secret_scanner,
        )

    def get_agent_config(self, name: str) -> Optional[AgentConfig]:
        """Get configuration for a specific agent"""
        return self.config.agents.get(name)

    def get_enabled_agents(self) -> Dict[str, AgentConfig]:
        """Get all enabled agent configurations"""
        return {k: v for k, v in self.config.agents.items() if v.enabled}

    def get_working_agents(self, agents_json_path: str = None) -> Dict[str, AgentConfig]:
        """Get agents that are actually working based on agents.json"""
        if not agents_json_path:
            agents_json_path = str(PROJECT_ROOT / "agents.json")

        import json
        if not os.path.exists(agents_json_path):
            return self.get_enabled_agents()

        with open(agents_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        working = {}
        for name, agent_data in data.get('agents', {}).items():
            if agent_data.get('working', False):
                if name in self.config.agents:
                    working[name] = self.config.agents[name]
        return working


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config(config_path: Optional[str] = None) -> ConfigManager:
    """Get global config manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_path)
    return _config_manager


def reload_config(config_path: Optional[str] = None) -> ConfigManager:
    """Reload configuration"""
    global _config_manager
    _config_manager = ConfigManager(config_path)
    return _config_manager