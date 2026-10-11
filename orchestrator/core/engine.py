"""Execution Engine with Retry Logic"""

import time
import uuid
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from orchestrator.core.config import get_config
from orchestrator.core.database import HistoryDatabase, TaskRecord
from orchestrator.core.analyzer import TaskAnalyzer, AgentSelector, TaskAnalysis
from orchestrator.adapters.factory import AdapterFactory
from orchestrator.adapters.base import ExecutionResult


@dataclass
class ExecutionContext:
    """Context for task execution"""
    task_id: str
    project_path: Path
    task_description: str
    selected_agent: str
    model: str
    analysis: TaskAnalysis
    attempt: int = 1
    max_attempts: int = 3
    start_time: float = field(default_factory=time.time)
    execution_log: List[str] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    test_results: str = ""
    errors: List[str] = field(default_factory=list)


class ExecutionEngine:
    """Main execution engine with retry logic"""

    def __init__(self, config=None):
        self.config = config or get_config()
        self.analyzer = TaskAnalyzer(self.config)
        self.selector = AgentSelector(self.config)
        self.factory = AdapterFactory(self.config)
        self.db = HistoryDatabase(self.config.config.history.db_path)

    def execute_task(self, project_path: str, task: str, agent_name: str = None,
                    model: str = None, max_attempts: int = None) -> Dict[str, Any]:
        """Execute a task with the specified or auto-selected agent"""

        project_path = Path(project_path).resolve()

        # Validate project path
        if not project_path.exists():
            return {
                'success': False,
                'error': f'Project path does not exist: {project_path}',
                'task_id': None
            }

        # Check git repo
        is_git = (project_path / '.git').exists()

        # Analyze task
        analysis = self.analyzer.analyze(str(project_path), task)

        # Get available adapters
        available_adapters = self.factory.get_available_adapters(str(project_path))

        if not available_adapters:
            return {
                'success': False,
                'error': 'No working agents available. Check agents.json and local model server.',
                'task_id': None
            }

        # Select agent
        if agent_name and agent_name in available_adapters:
            selected_agent = agent_name
            reason = "User specified"
        else:
            selected_agent, reason = self.selector.select(analysis, available_adapters)

        adapter = available_adapters[selected_agent]

        # Create task ID
        task_id = str(uuid.uuid4())[:8]

        # Create execution context
        context = ExecutionContext(
            task_id=task_id,
            project_path=project_path,
            task_description=task,
            selected_agent=selected_agent,
            model=model or "",
            analysis=analysis,
            max_attempts=max_attempts or self.config.general.max_retries
        )

        # Log start
        self._log(context, f"Starting task {task_id}")
        self._log(context, f"Project: {project_path}")
        self._log(context, f"Task: {task}")
        self._log(context, f"Analysis: {analysis.complexity} complexity, {analysis.estimated_size} size")
        self._log(context, f"Selected agent: {selected_agent} ({reason})")

        # Create git checkpoint if enabled and in git repo
        if self.config.config.execution.create_git_checkpoint and is_git:
            if adapter.create_git_checkpoint(f"Orchestrator checkpoint for task {task_id}"):
                self._log(context, "Created git checkpoint")

        # Execute with retry
        final_result = self._execute_with_retry(adapter, context)

        # Run tests if enabled
        if self.config.config.testing.run_after_changes and context.changed_files:
            self._run_tests(context, adapter)

        # Create final record
        record = self._create_task_record(context, final_result)

        # Save to history
        if self.config.config.history.enabled:
            self.db.add_task(record)
            self.db.cleanup_old_tasks(self.config.config.history.max_entries)

        return {
            'success': final_result.success,
            'task_id': task_id,
            'agent': selected_agent,
            'model': context.model,
            'attempts': context.attempt,
            'duration': time.time() - context.start_time,
            'changed_files': context.changed_files,
            'tests_run': context.test_results != "",
            'test_results': context.test_results,
            'errors': context.errors,
            'execution_log': context.execution_log
        }

    def _execute_with_retry(self, adapter, context: ExecutionContext) -> ExecutionResult:
        """Execute task with retry logic"""
        last_result = None

        for attempt in range(1, context.max_attempts + 1):
            context.attempt = attempt
            self._log(context, f"Attempt {attempt}/{context.max_attempts}")

            # Execute
            result = adapter.execute(
                context.task_description,
                context.model,
                timeout=self.config.config.general.default_timeout
            )

            # Add to context
            context.execution_log.extend(adapter.execution_log)
            context.changed_files = result.changed_files
            context.errors = result.errors

            last_result = result

            if result.success:
                self._log(context, f"Attempt {attempt} succeeded")
                break
            else:
                self._log(context, f"Attempt {attempt} failed: {result.errors}")

                # Analyze failure and prepare for retry
                if attempt < context.max_attempts:
                    retry_task = self._analyze_failure_and_prepare_retry(
                        context, result, attempt
                    )
                    if retry_task:
                        context.task_description = retry_task
                        self._log(context, f"Retrying with modified task")
                        time.sleep(2)  # Brief pause between retries
                    else:
                        self._log(context, "No retry strategy available")
                        break

        return last_result

    def _analyze_failure_and_prepare_retry(self, context: ExecutionContext,
                                           result: ExecutionResult, attempt: int) -> Optional[str]:
        """Analyze failure and prepare retry task"""
        errors = ' '.join(result.errors).lower()
        stdout = result.stdout.lower()
        stderr = result.stderr.lower()
        all_output = f"{stdout} {stderr} {errors}"

        # Build failure
        if any(kw in all_output for kw in ['build failed', 'compilation error', 'syntax error', 'cannot find module', 'import error', 'missing dependency']):
            return f"{context.task_description}\n\nPrevious attempt failed with build/compilation errors. Please fix the errors and ensure all dependencies are installed. Errors: {result.errors}"

        # Test failure
        if any(kw in all_output for kw in ['test failed', 'assertion error', 'test error', 'pytest failed', 'test failure']):
            return f"{context.task_description}\n\nPrevious attempt failed tests. Please fix the failing tests. Errors: {result.errors}"

        # Dependency failure
        if any(kw in all_output for kw in ['not found', 'missing', 'cannot find', 'no such file', 'module not found', 'package not found']):
            return f"{context.task_description}\n\nPrevious attempt failed due to missing dependencies/files. Please install required dependencies and create missing files. Errors: {result.errors}"

        # Permission/access error
        if any(kw in all_output for kw in ['permission denied', 'access denied', 'unauthorized']):
            return f"{context.task_description}\n\nPrevious attempt failed due to permission issues. Please ensure proper file permissions. Errors: {result.errors}"

        # Generic retry with error context
        if attempt < context.max_attempts:
            return f"{context.task_description}\n\nPrevious attempt failed. Please address the following errors: {result.errors}"

        return None

    def _run_tests(self, context: ExecutionContext, adapter):
        """Run tests for the project"""
        self._log(context, "Running tests...")

        try:
            # Detect test command
            test_cmd = self._detect_test_command(context.project_path)
            if not test_cmd:
                self._log(context, "No test command detected")
                return

            self._log(context, f"Running: {test_cmd}")

            result = subprocess.run(
                test_cmd,
                cwd=context.project_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                encoding='utf-8',
                errors='replace'
            )

            context.test_results = result.stdout
            if result.stderr:
                context.test_results += f"\nSTDERR:\n{result.stderr}"

            if result.returncode == 0:
                self._log(context, "Tests passed")
            else:
                self._log(context, f"Tests failed (exit code {result.returncode})")
                context.errors.append(f"Tests failed: {result.stderr[:500]}")

        except subprocess.TimeoutExpired:
            context.test_results = "Tests timed out"
            context.errors.append("Tests timed out after 120 seconds")
            self._log(context, "Tests timed out")
        except Exception as e:
            context.test_results = f"Test execution error: {e}"
            context.errors.append(f"Test execution error: {e}")
            self._log(context, f"Test error: {e}")

    def _detect_test_command(self, project_path: Path) -> Optional[str]:
        """Detect appropriate test command"""
        # Check package.json for npm test
        if (project_path / 'package.json').exists():
            import json
            with open(project_path / 'package.json') as f:
                data = json.load(f)
                if 'scripts' in data and 'test' in data['scripts']:
                    return 'npm test'

        # Check for pytest (use current interpreter: avoids Windows Store alias)
        if (project_path / 'pytest.ini').exists() or (project_path / 'pyproject.toml').exists() or list(project_path.glob('test_*.py')) or list(project_path.glob('*_test.py')):
            import sys
            return f'"{sys.executable}" -m pytest -v'

        # Check for cargo test
        if (project_path / 'Cargo.toml').exists():
            return 'cargo test'

        # Check for go test
        if (project_path / 'go.mod').exists():
            return 'go test ./...'

        # Check for dotnet test
        if list(project_path.glob('*.csproj')) or list(project_path.glob('*.sln')):
            return 'dotnet test'

        return None

    def _create_task_record(self, context: ExecutionContext, result: ExecutionResult) -> TaskRecord:
        """Create task record for history"""
        return TaskRecord(
            task_id=context.task_id,
            date=datetime.now().isoformat(),
            project_path=str(context.project_path),
            task_description=context.task_description,
            selected_agent=context.selected_agent,
            model=context.model,
            attempts=context.attempt,
            duration_seconds=time.time() - context.start_time,
            changed_files=context.changed_files,
            tests_run=context.test_results != "",
            test_results=context.test_results[:5000] if context.test_results else "",
            result="success" if result.success else "failed",
            errors="; ".join(context.errors) if context.errors else "",
            execution_log="\n".join(context.execution_log)
        )

    def _log(self, context: ExecutionContext, message: str):
        """Log message to context and console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        context.execution_log.append(log_entry)
        print(log_entry)