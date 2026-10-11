"""OpenCode Agent Adapter"""

import json
from typing import List, Dict, Any
from orchestrator.adapters.base import BaseAgentAdapter, ExecutionResult, AgentCapabilities


class OpenCodeAdapter(BaseAgentAdapter):
    """Adapter for OpenCode agent"""

    @property
    def agent_name(self) -> str:
        return "OpenCode"

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
        """Check if OpenCode is available"""
        try:
            import subprocess
            import os
            # Use full path from config or try common locations
            opencode_path = self.agent_config.path if self.agent_config and self.agent_config.path else 'opencode'
            if not os.path.isabs(opencode_path) and not opencode_path.endswith('.ps1'):
                # Try common npm locations
                possible_paths = [
                    os.path.expandvars(r'%APPDATA%\npm\opencode.ps1'),
                    os.path.expandvars(r'%APPDATA%\npm\opencode.cmd'),
                    'opencode'
                ]
                for p in possible_paths:
                    if os.path.exists(p):
                        opencode_path = p
                        break
            
            if opencode_path.endswith('.ps1'):
                result = subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-File', opencode_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            else:
                result = subprocess.run(
                    [opencode_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            return result.returncode == 0
        except Exception:
            return False

    def prepare_command(self, task: str, model: str = None, **kwargs) -> List[str]:
        """Prepare OpenCode command"""
        import os
        opencode_path = self.agent_config.path if self.agent_config and self.agent_config.path else 'opencode'
        if not os.path.isabs(opencode_path) and not opencode_path.endswith('.ps1'):
            possible_paths = [
                os.path.expandvars(r'%APPDATA%\npm\opencode.ps1'),
                os.path.expandvars(r'%APPDATA%\npm\opencode.cmd'),
                'opencode'
            ]
            for p in possible_paths:
                if os.path.exists(p):
                    opencode_path = p
                    break

        cmd = []
        if opencode_path.endswith('.ps1'):
            cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', opencode_path, 'run', task]
        else:
            cmd = [opencode_path, 'run', task]

        if model:
            # Bare local ids (from /v1/models discovery) need the configured
            # provider prefix (opencode format: provider/model). The provider
            # name comes from local_model_config (default "lmstudio").
            if "/" not in model and self.agent_config and self.agent_config.local_model_config:
                lm = self.agent_config.local_model_config
                if lm.get("model") == model:
                    pname = lm.get("provider_name") or "lmstudio"
                    model = f"{pname}/{model}"
            cmd.extend(['--model', model])

        if self.agent_config and self.agent_config.args:
            cmd.extend(self.agent_config.args)

        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_code: int = 0) -> ExecutionResult:
        """Parse OpenCode output"""
        # If exit code is 0, consider it success
        success = exit_code == 0

        # Try to detect errors
        errors = []
        if stderr and not success:
            for line in stderr.split('\n'):
                if 'error' in line.lower() or 'failed' in line.lower():
                    errors.append(line.strip())

        return ExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_seconds=0,  # Will be set by execute()
            changed_files=[],
            errors=errors
        )


class OpenCodeHeadlessAdapter(OpenCodeAdapter):
    """OpenCode adapter for headless/non-interactive mode"""

    def prepare_command(self, task: str, model: str = None, **kwargs) -> List[str]:
        """Prepare OpenCode command for headless mode"""
        cmd = ['opencode', 'run', task]

        if model:
            cmd.extend(['--model', model])

        # Add auto-approve for headless mode
        cmd.append('--auto')

        return cmd