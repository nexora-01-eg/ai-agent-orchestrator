"""Qwen Code Agent Adapter"""

from typing import List, Dict, Any
from orchestrator.adapters.base import BaseAgentAdapter, ExecutionResult, AgentCapabilities


class QwenAdapter(BaseAgentAdapter):
    """Adapter for Qwen Code agent"""

    @property
    def agent_name(self) -> str:
        return "Qwen"

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            file_read=True,
            file_write=True,
            file_edit=True,
            terminal_access=True,
            local_model=True,
            run_tests=True
        )

    def check_available(self) -> bool:
        """Check if Qwen Code is available"""
        try:
            import subprocess
            result = subprocess.run(
                ['qwen', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def prepare_command(self, task: str, model: str = None, **kwargs) -> List[str]:
        """Prepare Qwen Code command"""
        cmd = ['qwen']

        if task:
            cmd.extend(['-p', task])

        if model:
            cmd.extend(['-m', model])
        elif self.agent_config and self.agent_config.local_model_config:
            lm_config = self.agent_config.local_model_config
            if 'model' in lm_config:
                cmd.extend(['-m', lm_config['model']])
            if 'openai_base_url' in lm_config:
                cmd.extend(['--openai-base-url', lm_config['openai_base_url']])
            if 'openai_api_key' in lm_config:
                cmd.extend(['--openai-api-key', lm_config['openai_api_key']])
            if 'auth_type' in lm_config:
                cmd.extend(['--auth-type', lm_config['auth_type']])

        # Add args from config
        if self.agent_config and self.agent_config.args:
            cmd.extend(self.agent_config.args)

        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_code: int = 0) -> ExecutionResult:
        """Parse Qwen Code output"""
        success = exit_code == 0
        errors = []

        if stderr:
            for line in stderr.split('\n'):
                line_lower = line.lower()
                if 'error' in line_lower and 'warning' not in line_lower:
                    errors.append(line.strip())
                    success = False
                elif 'failed' in line_lower:
                    errors.append(line.strip())
                    success = False
                elif 'auth' in line_lower or 'authentication' in line_lower:
                    errors.append(line.strip())
                    success = False

        return ExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            exit_code=0 if success else 1,
            duration_seconds=0,
            changed_files=[],
            errors=errors
        )