"""Aider Agent Adapter"""

from typing import List, Dict, Any
from orchestrator.adapters.base import BaseAgentAdapter, ExecutionResult, AgentCapabilities


class AiderAdapter(BaseAgentAdapter):
    """Adapter for Aider agent"""

    @property
    def agent_name(self) -> str:
        return "Aider"

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
        """Check if Aider is available"""
        try:
            import subprocess
            result = subprocess.run(
                ['aider', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def prepare_command(self, task: str, model: str = None, **kwargs) -> List[str]:
        """Prepare Aider command.

        Local endpoint flags are ALWAYS included when configured: without
        --openai-api-base Aider silently targets the wrong backend.
        """
        cmd = ['aider']

        # Add message
        if task:
            cmd.extend(['--message', task])

        # Decide endpoint first: explicit CLOUD provider models keep cloud routing,
        # everything else (incl. bare ids) defaults to the local endpoint.
        # Without --openai-api-base Aider silently targets the wrong backend.
        cloud_markers = ("anthropic/", "openrouter/", "gemini/", "vertex_ai/",
                         "bedrock/", "azure/")
        use_local_endpoint = not model or not model.lower().startswith(cloud_markers)
        # Add model (explicit model wins). Bare local ids (e.g. from /v1/models
        # discovery) get the openai/ prefix so litellm routes them to the base.
        if model:
            if use_local_endpoint and "/" not in model:
                model = f"openai/{model}"
            cmd.extend(['--model', model])
        elif self.agent_config and self.agent_config.local_model_config:
            lm_config = self.agent_config.local_model_config
            if 'model' in lm_config:
                cmd.extend(['--model', lm_config['model']])
        if use_local_endpoint and self.agent_config and self.agent_config.local_model_config:
            lm_config = self.agent_config.local_model_config
            if 'openai_base_url' in lm_config:
                cmd.extend(['--openai-api-base', lm_config['openai_base_url']])
            if 'openai_api_key' in lm_config:
                cmd.extend(['--api-key', f"openai={lm_config['openai_api_key']}"])
            # Official model metadata: registers max_input_tokens/costs for the
            # local id in litellm's DB, so aider's sanity check finds model.info
            # and never shows "Unknown context window" nor offers the docs page
            # (which --yes-always would otherwise auto-open in a browser).
            from pathlib import Path as _P
            _meta = _P(__file__).parent.parent.parent / "aider-model-metadata.json"
            if _meta.exists():
                cmd.extend(['--model-metadata-file', str(_meta)])

        # Add args from config
        if self.agent_config and self.agent_config.args:
            cmd.extend(self.agent_config.args)

        # Yes always for non-interactive
        cmd.append('--yes-always')

        return cmd

    def parse_output(self, stdout: str, stderr: str, exit_code: int = 0) -> ExecutionResult:
        """Parse Aider output.

        Word-boundary matching: benign Windows console notes such as
        'UnicodeDecodeError' or 'prompt toolkit' must not fail a run
        whose exit code is 0.
        """
        import re as _re
        success = exit_code == 0
        errors = []

        def _is_error(text: str) -> bool:
            t = text.lower()
            if "warning" in t:
                return False
            return bool(_re.search(r"\berror\b|\bfailed\b|\bfailure\b|\bexception\b|\btraceback\b", t))

        if stderr:
            for line in stderr.split('\n'):
                if line.strip() and _is_error(line):
                    errors.append(line.strip())
                    success = False

        # NOTE: stdout is NEVER scanned for error words: aider echoes file
        # contents/diffs, and legitimate code (error handlers, `error = ...`)
        # would false-fail clean exit-0 runs. Real failures surface via
        # non-zero exit codes, stderr tracebacks, and the supervisor's
        # smoke/test gates.

        return ExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            exit_code=0 if success else 1,
            duration_seconds=0,
            changed_files=[],
            errors=errors
        )