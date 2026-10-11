"""Task Analysis and Agent Selection"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from orchestrator.core.config import get_config


@dataclass
class TaskAnalysis:
    """Analysis result for a task"""
    project_type: str
    language: str
    framework: str
    complexity: str  # low, medium, high
    files_likely_affected: List[str]
    required_commands: List[str]
    required_tests: List[str]
    risk_level: str  # low, medium, high
    estimated_size: str  # small, medium, large
    is_git_focused: bool = False
    is_multi_file: bool = False
    needs_local_model: bool = False


class TaskAnalyzer:
    """Analyzes tasks to determine best approach"""

    def __init__(self, config=None):
        self.config = config or get_config()

    def analyze(self, project_path: str, task: str) -> TaskAnalysis:
        """Analyze a task and project"""
        project_path = Path(project_path).resolve()
        task_lower = task.lower()

        # Detect project type
        project_type = self._detect_project_type(project_path)

        # Detect language
        language = self._detect_language(project_path)

        # Detect framework
        framework = self._detect_framework(project_path, language)

        # Analyze task complexity
        complexity = self._analyze_complexity(task_lower)

        # Estimate files affected
        files_likely = self._estimate_files_affected(task_lower, project_path)

        # Required commands
        commands = self._estimate_commands(task_lower, language, framework)

        # Required tests
        tests = self._estimate_tests(task_lower, language, framework)

        # Risk level
        risk = self._analyze_risk(task_lower)

        # Estimated size
        size = self._estimate_size(task_lower, len(files_likely))

        # Git-focused
        is_git = any(kw in task_lower for kw in ['git', 'commit', 'branch', 'merge', 'diff', 'history'])

        # Multi-file
        is_multi = len(files_likely) > 3 or any(kw in task_lower for kw in ['system', 'complete', 'full', 'entire', 'refactor', 'architecture'])

        # Needs local model
        needs_local = self.config.config.agent_preferences.prefer_local_models

        return TaskAnalysis(
            project_type=project_type,
            language=language,
            framework=framework,
            complexity=complexity,
            files_likely_affected=files_likely,
            required_commands=commands,
            required_tests=tests,
            risk_level=risk,
            estimated_size=size,
            is_git_focused=is_git,
            is_multi_file=is_multi,
            needs_local_model=needs_local
        )

    def _detect_project_type(self, project_path: Path) -> str:
        """Detect project type from files"""
        if (project_path / 'package.json').exists():
            return 'node'
        elif (project_path / 'pyproject.toml').exists() or (project_path / 'setup.py').exists() or (project_path / 'requirements.txt').exists():
            return 'python'
        elif (project_path / 'Cargo.toml').exists():
            return 'rust'
        elif (project_path / 'go.mod').exists():
            return 'go'
        elif (project_path / 'pom.xml').exists() or (project_path / 'build.gradle').exists():
            return 'java'
        elif (project_path / '*.csproj').exists() or (project_path / '*.sln').exists():
            return 'dotnet'
        else:
            return 'unknown'

    def _detect_language(self, project_path: Path) -> str:
        """Detect primary programming language"""
        extensions = {}
        for file in project_path.rglob('*'):
            if file.is_file() and file.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx', '.rs', '.go', '.java', '.cs', '.cpp', '.c', '.h']:
                extensions[file.suffix] = extensions.get(file.suffix, 0) + 1

        if not extensions:
            return 'unknown'

        # Map extension to language
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.rs': 'rust',
            '.go': 'go',
            '.java': 'java',
            '.cs': 'csharp',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c'
        }

        max_ext = max(extensions, key=extensions.get)
        return lang_map.get(max_ext, 'unknown')

    def _detect_framework(self, project_path: Path, language: str) -> str:
        """Detect framework"""
        if language == 'python':
            if (project_path / 'requirements.txt').exists():
                with open(project_path / 'requirements.txt') as f:
                    content = f.read().lower()
                    if 'django' in content:
                        return 'django'
                    elif 'flask' in content:
                        return 'flask'
                    elif 'fastapi' in content:
                        return 'fastapi'
            if (project_path / 'pyproject.toml').exists():
                with open(project_path / 'pyproject.toml') as f:
                    content = f.read().lower()
                    if 'django' in content:
                        return 'django'
                    elif 'flask' in content:
                        return 'flask'
        elif language == 'javascript' or language == 'typescript':
            if (project_path / 'package.json').exists():
                with open(project_path / 'package.json') as f:
                    content = f.read().lower()
                    if 'react' in content:
                        return 'react'
                    elif 'vue' in content:
                        return 'vue'
                    elif 'next' in content:
                        return 'nextjs'
                    elif 'express' in content:
                        return 'express'
                    elif 'nest' in content:
                        return 'nestjs'
        elif language == 'rust':
            return 'rust'
        elif language == 'go':
            return 'go'
        elif language == 'csharp':
            return 'dotnet'

        return 'none'

    def _analyze_complexity(self, task: str) -> str:
        """Analyze task complexity"""
        high_keywords = ['system', 'architecture', 'refactor', 'migrate', 'complete', 'full', 'entire', 'authentication', 'authorization', 'security', 'distributed', 'microservice']
        medium_keywords = ['feature', 'component', 'module', 'api', 'service', 'integration', 'database', 'test', 'crud']

        if any(kw in task for kw in high_keywords):
            return 'high'
        elif any(kw in task for kw in medium_keywords):
            return 'medium'
        return 'low'

    def _estimate_files_affected(self, task: str, project_path: Path) -> List[str]:
        """Estimate files likely to be affected"""
        files = []

        # Common patterns
        patterns = {
            'auth': ['auth', 'login', 'register', 'token', 'jwt', 'session'],
            'api': ['api', 'endpoint', 'route', 'controller'],
            'database': ['model', 'schema', 'migration', 'db', 'database'],
            'frontend': ['component', 'page', 'view', 'ui', 'form'],
            'test': ['test', 'spec', '__tests__'],
            'config': ['config', 'settings', 'env'],
        }

        for category, keywords in patterns.items():
            if any(kw in task for kw in keywords):
                files.append(f"{category}/*")

        # If multi-file task
        if any(kw in task for kw in ['system', 'complete', 'full', 'refactor', 'architecture']):
            files.append('multiple files across project')

        return files if files else ['unknown']

    def _estimate_commands(self, task: str, language: str, framework: str) -> List[str]:
        """Estimate required commands"""
        commands = []

        if 'install' in task or 'dependency' in task or 'package' in task:
            if language == 'python':
                commands.append('pip install')
            elif language in ['javascript', 'typescript']:
                commands.append('npm install')
            elif language == 'rust':
                commands.append('cargo add')
            elif language == 'go':
                commands.append('go get')

        if 'test' in task:
            commands.append(self._get_test_command(language))

        if 'build' in task or 'compile' in task:
            if language == 'python':
                commands.append('python -m build')
            elif language in ['javascript', 'typescript']:
                commands.append('npm run build')
            elif language == 'rust':
                commands.append('cargo build')
            elif language == 'go':
                commands.append('go build')

        if 'run' in task or 'start' in task:
            if language in ['javascript', 'typescript']:
                commands.append('npm start')
            elif language == 'python':
                commands.append('python main.py')

        return commands

    def _get_test_command(self, language: str) -> str:
        """Get test command for language"""
        commands = {
            'python': 'pytest',
            'javascript': 'npm test',
            'typescript': 'npm test',
            'rust': 'cargo test',
            'go': 'go test ./...',
            'csharp': 'dotnet test',
            'java': 'mvn test',
        }
        return commands.get(language, 'unknown')

    def _estimate_tests(self, task: str, language: str, framework: str) -> List[str]:
        """Estimate required tests"""
        tests = []

        if 'test' in task:
            tests.append(f'{language} unit tests')

        if 'integration' in task:
            tests.append('integration tests')

        if 'api' in task or 'endpoint' in task:
            tests.append('API tests')

        if 'component' in task and framework in ['react', 'vue']:
            tests.append('component tests')

        return tests

    def _analyze_risk(self, task: str) -> str:
        """Analyze risk level"""
        high_risk = ['delete', 'remove', 'drop', 'truncate', 'format', 'migrate', 'production', 'database', 'schema', 'auth', 'security', 'permission']
        medium_risk = ['modify', 'change', 'update', 'refactor', 'rename', 'move']

        if any(kw in task for kw in high_risk):
            return 'high'
        elif any(kw in task for kw in medium_risk):
            return 'medium'
        return 'low'

    def _estimate_size(self, task: str, file_count: int) -> str:
        """Estimate task size"""
        if file_count > 10 or any(kw in task for kw in ['system', 'complete', 'full', 'architecture', 'refactor all']):
            return 'large'
        elif file_count > 3 or any(kw in task for kw in ['feature', 'module', 'component', 'api']):
            return 'medium'
        return 'small'


class AgentSelector:
    """Selects the best agent for a task"""

    def __init__(self, config=None):
        self.config = config or get_config()

    def select(self, analysis: TaskAnalysis, available_agents: Dict[str, Any]) -> Tuple[str, str]:
        """
        Select best agent for task.
        Returns (agent_name, reason)
        """
        scores = {}

        for name, adapter in available_agents.items():
            score = 0
            reasons = []

            # Base score for working agents
            score += 10

            # Local model preference
            if analysis.needs_local_model and adapter.get_capabilities().local_model:
                score += 15
                reasons.append("Supports local models")

            # Git-focused tasks -> Aider
            if analysis.is_git_focused and name == 'Aider':
                score += 20
                reasons.append("Git-native workflow")

            # Large multi-file tasks -> OpenCode
            if analysis.estimated_size == 'large' and analysis.is_multi_file and name == 'OpenCode':
                score += 15
                reasons.append("Good for large multi-file tasks")

            # Simple coding tasks -> any
            if analysis.estimated_size == 'small' and not analysis.is_git_focused:
                if name == 'OpenCode':
                    score += 10
                    reasons.append("General purpose")

            # Qwen for agent teams / complex orchestration
            if analysis.complexity == 'high' and name == 'Qwen':
                score += 10
                reasons.append("Supports agent teams")

            # Prefer free agents
            agent_config = self.config.get_agent_config(name)
            if agent_config and agent_config.free_tier:
                score += 5

            scores[name] = (score, reasons)

        if not scores:
            # Fallback to first available
            first = list(available_agents.keys())[0]
            return first, "Default fallback"

        # Select highest score
        best = max(scores.items(), key=lambda x: x[1][0])
        agent_name = best[0]
        reason = "; ".join(best[1][1]) if best[1][1] else "Highest score"

        return agent_name, reason