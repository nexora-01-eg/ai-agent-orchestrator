"""LM Studio Local Model Adapter"""

import requests
import json
import subprocess
import os
from typing import List, Dict, Any, Optional
from orchestrator.adapters.base import BaseAgentAdapter, ExecutionResult, AgentCapabilities


class LMStudioAdapter(BaseAgentAdapter):
    """Adapter for LM Studio local model server"""

    @property
    def agent_name(self) -> str:
        return "LM Studio"

    def get_capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(
            file_read=False,
            file_write=False,
            file_edit=False,
            terminal_access=False,
            local_model=True,
            run_tests=False
        )

    def check_available(self) -> bool:
        """Check if LM Studio is running and accessible"""
        try:
            config = self.config.config.local_models.lm_studio
            response = requests.get(
                f"{config.url}/models",
                headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else {},
                timeout=5
            )
            if response.status_code == 200:
                return True
        except Exception:
            pass
        
        # Check if LM Studio process is running
        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq "LM Studio.exe"'], capture_output=True, text=True)
            return "LM Studio.exe" in result.stdout
        except Exception:
            pass
        
        return False

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models from LM Studio"""
        try:
            config = self.config.config.local_models.lm_studio
            response = requests.get(
                f"{config.url}/models",
                headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else {},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
        except Exception as e:
            self._log(f"Error fetching models: {e}")
        return []

    def get_coding_models(self) -> List[Dict[str, Any]]:
        """Filter models suitable for coding"""
        all_models = self.get_available_models()
        coding_keywords = ['coder', 'code', 'coding', 'program', 'python', 'javascript', 'qwen', 'deepseek', 'phi', 'starcoder', 'wizardcoder', 'codellama']
        coding_models = []

        for model in all_models:
            model_id = model.get('id', '').lower()
            if any(kw in model_id for kw in coding_keywords):
                coding_models.append(model)

        return coding_models

    def recommend_model(self) -> Optional[str]:
        """Recommend the best coding model"""
        coding_models = self.get_coding_models()
        if not coding_models:
            return None

        # Prefer qwen2.5-coder, then deepseek-coder, then others
        priority = ['qwen2.5-coder', 'deepseek-coder', 'starcoder', 'wizardcoder', 'codellama', 'phi']
        for p in priority:
            for model in coding_models:
                if p in model.get('id', '').lower():
                    return model['id']

        # Return first coding model
        return coding_models[0].get('id') if coding_models else None

    def prepare_command(self, task: str, model: str = None, **kwargs) -> List[str]:
        """LM Studio doesn't run commands directly, it's an API server"""
        return []

    def parse_output(self, stdout: str, stderr: str) -> ExecutionResult:
        """Not used for LM Studio"""
        return ExecutionResult(
            success=True,
            stdout=stdout,
            stderr=stderr,
            exit_code=0,
            duration_seconds=0,
            changed_files=[],
            errors=[]
        )

    def chat_completion(self, messages: List[Dict[str, str]], model: str = None,
                       temperature: float = 0.7, max_tokens: int = 4096) -> Optional[Dict]:
        """Send chat completion request to LM Studio"""
        try:
            config = self.config.config.local_models.lm_studio
            model_name = model or self.recommend_model()

            if not model_name:
                self._log("No suitable model found in LM Studio")
                return None

            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }

            response = requests.post(
                f"{config.url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.api_key}" if config.api_key else ""
                },
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                return response.json()
            else:
                self._log(f"LM Studio error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            self._log(f"LM Studio request failed: {e}")
            return None