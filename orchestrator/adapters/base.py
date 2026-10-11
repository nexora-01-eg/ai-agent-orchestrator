"""Base Agent Adapter Interface"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
import subprocess
import time


@dataclass
class ExecutionResult:
    """Result of agent execution"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    changed_files: List[str]
    errors: List[str]


@dataclass
class AgentCapabilities:
    """Agent capabilities"""
    file_read: bool = False
    file_write: bool = False
    file_edit: bool = False
    terminal_access: bool = False
    local_model: bool = False
    run_tests: bool = False


class BaseAgentAdapter(ABC):
    """Base class for all agent adapters"""

    def __init__(self, config, project_path: str):
        self.config = config
        self.project_path = Path(project_path).resolve()
        self.agent_config = config.get_agent_config(self.agent_name)
        self.execution_log = []

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the agent name"""
        pass

    @abstractmethod
    def get_capabilities(self) -> AgentCapabilities:
        """Return agent capabilities"""
        pass

    @abstractmethod
    def check_available(self) -> bool:
        """Check if agent is available and working"""
        pass

    @abstractmethod
    def prepare_command(self, task: str, model: str = None, **kwargs) -> List[str]:
        """Prepare the command to execute the agent"""
        pass

    @abstractmethod
    def parse_output(self, stdout: str, stderr: str) -> ExecutionResult:
        """Parse agent output into ExecutionResult"""
        pass

    def execute(self, task: str, model: str = None, timeout: int = 300, **kwargs) -> ExecutionResult:
        """Execute the agent with the given task"""
        cmd = self.prepare_command(task, model, **kwargs)
        self._log(f"Executing: {' '.join(cmd)}")

        start_time = time.time()
        try:
            # Set up environment
            env = os.environ.copy()
            if self.agent_config and self.agent_config.env:
                env.update(self.agent_config.env)

            # Add project path to env
            env['PROJECT_PATH'] = str(self.project_path)

            process = subprocess.Popen(
                cmd,
                cwd=self.project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                encoding='utf-8',
                errors='replace'
            )

            stdout, stderr = process.communicate(timeout=timeout)
            duration = time.time() - start_time

            self._log(f"Exit code: {process.returncode}")
            self._log(f"Duration: {duration:.2f}s")

            result = self.parse_output(stdout, stderr, process.returncode)
            result.duration_seconds = duration

            # Detect changed files
            result.changed_files = self._detect_changed_files()

            return result

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            duration = time.time() - start_time
            self._log(f"TIMEOUT after {duration:.2f}s")
            return ExecutionResult(
                success=False,
                stdout=stdout or '',
                stderr=stderr or 'Execution timeout',
                exit_code=-1,
                duration_seconds=duration,
                changed_files=[],
                errors=['Execution timeout']
            )
        except Exception as e:
            duration = time.time() - start_time
            self._log(f"ERROR: {str(e)}")
            return ExecutionResult(
                success=False,
                stdout='',
                stderr=str(e),
                exit_code=-1,
                duration_seconds=duration,
                changed_files=[],
                errors=[str(e)]
            )

    def _detect_changed_files(self) -> List[str]:
        """Detect files changed during execution using git status"""
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                files = []
                # NOTE: do NOT strip() the whole output: it eats the leading
                # status column of the first line (" M f" -> "M f" -> "alc.py").
                for line in result.stdout.splitlines():
                    if not line.strip():
                        continue
                    # porcelain v1: XY<space>path (XY varies: ' M', 'M ', '??', 'A ', ...)
                    # path starts after the first 3 characters
                    path = line[3:].strip() if len(line) > 3 else line.strip()
                    # handle rename format "old -> new"
                    if " -> " in path:
                        path = path.split(" -> ")[-1].strip().strip('"')
                    path = path.strip('"')
                    if not path:
                        continue
                    # Ignore agent metadata / caches: they are never "work".
                    # (Aider writes .aider*; pytest writes __pycache__.)
                    low = path.replace("\\", "/").lower()
                    if low.startswith(".aider") or low.startswith("__pycache__/") or \
                       "/__pycache__/" in low or low.startswith(".pytest_cache/"):
                        continue
                    files.append(path)
                return files
        except Exception:
            pass
        return []

    def create_git_checkpoint(self, message: str = "Orchestrator checkpoint") -> bool:
        """Create a git checkpoint before execution"""
        try:
            # Check if we're in a git repo
            subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=self.project_path,
                capture_output=True,
                check=True
            )

            # Add all changes
            subprocess.run(
                ['git', 'add', '-A'],
                cwd=self.project_path,
                capture_output=True,
                check=True
            )

            # Commit
            result = subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def _log(self, message: str):
        """Add message to execution log"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}"
        self.execution_log.append(log_entry)
        print(log_entry)

    def get_execution_log(self) -> str:
        """Get full execution log"""
        return '\n'.join(self.execution_log)


# Import datetime for logging
from datetime import datetime
import os