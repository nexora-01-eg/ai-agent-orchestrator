"""Project Analyzer - Analyzes project structure and creates ProjectProfile"""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProjectProfile:
    """Profile of a project after analysis"""
    path: str
    name: str
    language: str
    framework: str
    package_manager: str
    build_system: str
    test_framework: str
    git_status: str
    project_size: str
    num_files: int
    num_dirs: int
    important_directories: List[str]
    config_files: List[str]
    existing_tests: bool
    test_count: int
    dependencies: Dict[str, str]
    has_dockerfile: bool
    has_readme: bool
    git_branch: str
    git_clean: bool
    analyzed_at: str


class ProjectAnalyzer:
    """Analyzes project structure and creates ProjectProfile"""

    LANGUAGE_PATTERNS = {
        'python': ['.py'],
        'javascript': ['.js', '.jsx'],
        'typescript': ['.ts', '.tsx'],
        'rust': ['.rs'],
        'go': ['.go'],
        'java': ['.java'],
        'csharp': ['.cs'],
        'cpp': ['.cpp', '.cc', '.cxx'],
        'c': ['.c', '.h'],
        'ruby': ['.rb'],
        'php': ['.php'],
        'swift': ['.swift'],
        'kotlin': ['.kt'],
        'scala': ['.scala'],
    }

    FRAMEWORK_PATTERNS = {
        'python': {
            'django': ['django'],
            'flask': ['flask'],
            'fastapi': ['fastapi'],
            'tornado': ['tornado'],
            'pyramid': ['pyramid'],
            'starlette': ['starlette'],
        },
        'javascript': {
            'react': ['react'],
            'vue': ['vue'],
            'nextjs': ['next'],
            'express': ['express'],
            'nestjs': ['@nestjs'],
            'angular': ['@angular'],
            'svelte': ['svelte'],
            'nuxt': ['nuxt'],
            'remix': ['@remix'],
            'astro': ['astro'],
        },
        'typescript': {
            'react': ['react'],
            'vue': ['vue'],
            'nextjs': ['next'],
            'nestjs': ['@nestjs'],
            'angular': ['@angular'],
        },
        'rust': {
            'actix': ['actix-web'],
            'axum': ['axum'],
            'rocket': ['rocket'],
            'warp': ['warp'],
        },
        'go': {
            'gin': ['gin'],
            'echo': ['echo'],
            'fiber': ['fiber'],
            'chi': ['chi'],
        },
        'java': {
            'spring': ['spring'],
            'spring-boot': ['spring-boot'],
            'quarkus': ['quarkus'],
            'micronaut': ['micronaut'],
        },
        'csharp': {
            'aspnet': ['aspnetcore'],
            'entity-framework': ['entityframework'],
        },
    }

    CONFIG_FILES = {
        'package.json': 'npm',
        'package-lock.json': 'npm',
        'yarn.lock': 'yarn',
        'pnpm-lock.yaml': 'pnpm',
        'requirements.txt': 'pip',
        'pyproject.toml': 'pip/poetry',
        'setup.py': 'pip',
        'Pipfile': 'pipenv',
        'poetry.lock': 'poetry',
        'Cargo.toml': 'cargo',
        'Cargo.lock': 'cargo',
        'go.mod': 'go',
        'go.sum': 'go',
        'pom.xml': 'maven',
        'build.gradle': 'gradle',
        'build.gradle.kts': 'gradle',
        'settings.gradle': 'gradle',
        'composer.json': 'composer',
        'Gemfile': 'bundler',
        'Gemfile.lock': 'bundler',
    }

    BUILD_FILES = {
        'Makefile': 'make',
        'CMakeLists.txt': 'cmake',
        'build.gradle': 'gradle',
        'build.gradle.kts': 'gradle',
        'pom.xml': 'maven',
        'Cargo.toml': 'cargo',
        'go.mod': 'go',
        'package.json': 'npm',
        'pyproject.toml': 'pip/poetry',
        'setup.py': 'pip',
        'CMakeLists.txt': 'cmake',
        'meson.build': 'meson',
        'build.bazel': 'bazel',
        'BUILD': 'bazel',
    }

    TEST_PATTERNS = {
        'python': {
            'pytest': ['pytest', 'test_*.py', '*_test.py', 'tests/'],
            'unittest': ['unittest', 'test*.py'],
        },
        'javascript': {
            'jest': ['jest', '__tests__', '*.test.js', '*.spec.js'],
            'mocha': ['mocha', 'test/', 'spec/'],
            'vitest': ['vitest', '*.test.ts', '*.spec.ts'],
            'cypress': ['cypress'],
        },
        'typescript': {
            'jest': ['jest', '__tests__', '*.test.ts', '*.spec.ts'],
            'vitest': ['vitest', '*.test.ts', '*.spec.ts'],
        },
        'rust': {
            'cargo': ['cargo test', '#[test]'],
        },
        'go': {
            'go test': ['_test.go'],
        },
        'java': {
            'junit': ['junit', 'Test.java'],
            'testng': ['testng'],
        },
        'csharp': {
            'nunit': ['nunit', 'Test.cs'],
            'xunit': ['xunit'],
            'mstest': ['mstest'],
        },
        'rust': {
            'cargo': ['cargo test'],
        },
        'go': {
            'go test': ['_test.go'],
        },
    }

    def __init__(self):
        pass

    def analyze(self, project_path: str) -> ProjectProfile:
        """Analyze project and create profile"""
        path = Path(project_path).resolve()
        
        if not path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        # Basic info
        name = path.name
        
        # Detect language
        language = self._detect_language(path)
        
        # Detect framework
        framework = self._detect_framework(path, language)
        
        # Detect package manager
        package_manager = self._detect_package_manager(path)
        
        # Detect build system
        build_system = self._detect_build_system(path)
        
        # Detect test framework
        test_framework = self._detect_test_framework(path, language)
        
        # Git status
        git_status = self._get_git_status(path)
        git_branch, git_clean = self._get_git_details(path)
        
        # Project size
        num_files, num_dirs, project_size = self._analyze_size(path)
        
        # Important directories
        important_dirs = self._find_important_directories(path)
        
        # Config files
        config_files = self._find_config_files(path)
        
        # Existing tests
        existing_tests, test_count = self._analyze_tests(path, language)
        
        # Dependencies
        dependencies = self._extract_dependencies(path, language, package_manager)
        
        # Dockerfile
        has_dockerfile = (path / 'Dockerfile').exists() or (path / 'docker-compose.yml').exists() or (path / 'docker-compose.yaml').exists()
        
        # README
        has_readme = self._has_readme(path)
        
        profile = ProjectProfile(
            path=str(path),
            name=name,
            language=language,
            framework=framework,
            package_manager=package_manager,
            build_system=build_system,
            test_framework=test_framework,
            git_status=git_status,
            project_size=project_size,
            num_files=num_files,
            num_dirs=num_dirs,
            important_directories=important_dirs,
            config_files=config_files,
            existing_tests=existing_tests,
            test_count=test_count,
            dependencies=dependencies,
            has_dockerfile=has_dockerfile,
            has_readme=has_readme,
            git_branch=git_branch,
            git_clean=git_clean,
            analyzed_at=datetime.now().isoformat()
        )
        
        return profile

    def _detect_language(self, path: Path) -> str:
        """Detect primary programming language"""
        extensions = {}
        
        for ext, lang in self.LANGUAGE_PATTERNS.items():
            count = 0
            for pattern in lang:
                count += len(list(path.rglob(f'*{pattern}')))
            if count > 0:
                extensions[ext] = count
        
        if not extensions:
            return 'unknown'
        
        # Return language with most files
        return max(extensions, key=extensions.get)

    def _detect_framework(self, path: Path, language: str) -> str:
        """Detect framework from config files"""
        if language not in self.FRAMEWORK_PATTERNS:
            return 'none'
        
        # Check package.json for JS/TS frameworks
        if language in ['javascript', 'typescript']:
            pkg_path = path / 'package.json'
            if pkg_path.exists():
                try:
                    with open(pkg_path) as f:
                        pkg = json.load(f)
                    deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
                    for framework, keywords in self.FRAMEWORK_PATTERNS[language].items():
                        for keyword in keywords:
                            for dep in deps:
                                if keyword in dep:
                                    return framework
                except:
                    pass
        
        # Check Python requirements
        if language == 'python':
            for req_file in ['requirements.txt', 'pyproject.toml', 'setup.py', 'Pipfile']:
                req_path = path / req_file
                if req_path.exists():
                    try:
                        content = req_path.read_text().lower()
                        for framework, keywords in self.FRAMEWORK_PATTERNS[language].items():
                            for keyword in keywords:
                                if keyword in content:
                                    return framework
                    except:
                        pass
        
        return 'none'

    def _detect_package_manager(self, path: Path) -> str:
        """Detect package manager"""
        for config_file, manager in self.CONFIG_FILES.items():
            if (path / config_file).exists():
                return manager
        return 'unknown'

    def _detect_build_system(self, path: Path) -> str:
        """Detect build system"""
        for build_file, system in self.BUILD_FILES.items():
            if (path / build_file).exists():
                return system
        return 'unknown'

    def _detect_test_framework(self, path: Path, language: str) -> str:
        """Detect test framework"""
        if language not in self.TEST_PATTERNS:
            return 'unknown'
        
        for framework, patterns in self.TEST_PATTERNS[language].items():
            for pattern in patterns:
                # Check for config files
                if pattern in ['pytest', 'jest', 'vitest', 'mocha', 'cargo test', 'go test']:
                    config_files = {
                        'pytest': ['pytest.ini', 'pyproject.toml', 'tox.ini'],
                        'jest': ['jest.config.js', 'jest.config.ts', 'package.json'],
                        'vitest': ['vitest.config.ts', 'vitest.config.js'],
                        'mocha': ['mocha.opts', '.mocharc.js'],
                    }
                    if framework in config_files:
                        for cf in config_files[framework]:
                            if (path / cf).exists():
                                return framework
                    # Check package.json for npm-based
                    if framework in ['jest', 'vitest', 'mocha']:
                        pkg_path = path / 'package.json'
                        if pkg_path.exists():
                            try:
                                with open(pkg_path) as f:
                                    pkg = json.load(f)
                                scripts = pkg.get('scripts', {})
                                if 'test' in scripts and framework in scripts['test']:
                                    return framework
                            except:
                                pass
                # Check for test files
                else:
                    matches = list(path.rglob(pattern))
                    if matches:
                        return framework
        
        return 'unknown'

    def _get_git_status(self, path: Path) -> str:
        """Get git status summary"""
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split('\n') if l]
                if not lines:
                    return 'clean'
                return f'{len(lines)} changes'
            return 'no git'
        except:
            return 'error'

    def _get_git_details(self, path: Path) -> tuple:
        """Get git branch and clean status"""
        try:
            # Get branch
            branch_result = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else 'unknown'
            
            # Get clean status
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=5
            )
            clean = len(status_result.stdout.strip()) == 0 if status_result.returncode == 0 else False
            
            return branch, clean
        except:
            return 'unknown', False

    def _analyze_size(self, path: Path) -> tuple:
        """Analyze project size"""
        num_files = 0
        num_dirs = 0
        
        # Skip common ignore directories
        ignore_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', 'dist', 'build', 'target', '.next', '.cache'}
        
        for item in path.rglob('*'):
            # Check if any parent is in ignore_dirs
            if any(part in ignore_dirs for part in item.parts):
                continue
            
            if item.is_file():
                num_files += 1
            elif item.is_dir():
                num_dirs += 1
        
        if num_files < 50:
            size = 'small'
        elif num_files < 500:
            size = 'medium'
        elif num_files < 5000:
            size = 'large'
        else:
            size = 'xlarge'
        
        return num_files, num_dirs, size

    def _find_important_directories(self, path: Path) -> List[str]:
        """Find important project directories"""
        important = []
        common_dirs = ['src', 'lib', 'app', 'tests', 'test', 'spec', 'docs', 'doc', 'scripts', 'bin', 'config', 'configs', 'assets', 'static', 'public', 'components', 'pages', 'views', 'models', 'controllers', 'services', 'utils', 'helpers', 'api', 'routes', 'middleware', 'config', 'constants', 'types', 'interfaces', 'schemas', 'validators', 'decorators', 'guards', 'pipes', 'filters', 'interceptors', 'modules', 'plugins', 'extensions', 'addons']
        
        for item in path.iterdir():
            if item.is_dir() and item.name in common_dirs:
                important.append(item.name)
        
        return important

    def _find_config_files(self, path: Path) -> List[str]:
        """Find configuration files"""
        configs = []
        for config_file in self.CONFIG_FILES.keys():
            if (path / config_file).exists():
                configs.append(config_file)
        # Add common config files
        for item in path.iterdir():
            if item.is_file() and item.name.endswith(('.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.config', '.env', '.env.example', '.env.local')):
                if item.name not in configs:
                    configs.append(item.name)
        return configs

    def _analyze_tests(self, path: Path, language: str) -> tuple:
        """Analyze existing tests"""
        if language not in self.TEST_PATTERNS:
            return False, 0
        
        test_files = []
        for framework, patterns in self.TEST_PATTERNS.get(language, {}).items():
            for pattern in patterns:
                matches = list(path.rglob(pattern))
                test_files.extend(matches)
        
        return len(test_files) > 0, len(test_files)

    def _extract_dependencies(self, path: Path, language: str, package_manager: str) -> Dict[str, str]:
        """Extract project dependencies"""
        deps = {}
        
        try:
            if language == 'python':
                # requirements.txt
                req_path = path / 'requirements.txt'
                if req_path.exists():
                    for line in req_path.read_text().splitlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Parse package name
                            pkg = re.split(r'[<>=!~]', line)[0].strip()
                            if pkg:
                                deps[pkg] = 'requirements.txt'
                
                # pyproject.toml
                pyproject_path = path / 'pyproject.toml'
                if pyproject_path.exists():
                    try:
                        import tomli
                        with open(pyproject_path, 'rb') as f:
                            data = tomli.load(f)
                        for dep in data.get('project', {}).get('dependencies', []):
                            pkg = re.split(r'[<>=!~]', dep)[0].strip()
                            if pkg:
                                deps[pkg] = 'pyproject.toml'
                        for dep in data.get('tool', {}).get('poetry', {}).get('dependencies', {}):
                            if dep != 'python':
                                deps[dep] = 'poetry'
                    except:
                        pass
                        
            elif language in ['javascript', 'typescript']:
                pkg_path = path / 'package.json'
                if pkg_path.exists():
                    try:
                        with open(pkg_path) as f:
                            pkg = json.load(f)
                        for dep_name, version in {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}.items():
                            deps[dep_name] = version
                    except:
                        pass
                        
            elif language == 'rust':
                cargo_path = path / 'Cargo.toml'
                if cargo_path.exists():
                    try:
                        import tomli
                        with open(cargo_path, 'rb') as f:
                            data = tomli.load(f)
                        for dep_name, dep_info in data.get('dependencies', {}).items():
                            if isinstance(dep_info, str):
                                deps[dep_name] = dep_info
                            elif isinstance(dep_info, dict):
                                deps[dep_name] = dep_info.get('version', 'unknown')
                    except:
                        pass
                        
            elif language == 'go':
                go_mod_path = path / 'go.mod'
                if go_mod_path.exists():
                    content = go_mod_path.read_text()
                    for line in content.splitlines():
                        line = line.strip()
                        if line and not line.startswith('//') and not line.startswith('module') and not line.startswith('go '):
                            parts = line.split()
                            if len(parts) >= 2:
                                deps[parts[0]] = parts[1]
                                
        except Exception:
            pass
        
        return deps

    def _has_readme(self, path: Path) -> bool:
        """Check if README exists"""
        for name in ['README.md', 'README.rst', 'README.txt', 'README', 'readme.md', 'readme.rst']:
            if (path / name).exists():
                return True
        return False