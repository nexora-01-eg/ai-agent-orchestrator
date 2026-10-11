"""Task Planner - decomposes a task into objective + subtasks (rule-based, offline)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict
import re


@dataclass
class TaskProfile:
    objective: str
    subtasks: List[str]
    affected_areas: List[str]
    expected_files: List[str]
    required_tools: List[str]
    testing_requirements: List[str]
    complexity: str
    risk: str
    network_required: bool
    model_requirement: str  # small | coder-7b | large
    execution_mode: str = "AUTO"


_AUTH_RE = re.compile(r"auth|login|register|jwt|token|session|oauth|password", re.I)
_API_RE = re.compile(r"\bapi\b|endpoint|route|controller|rest|graphql", re.I)
_DB_RE = re.compile(r"\bdatabase\b|\bdb\b|model|schema|migration|sql|sqlite|postgres|mongo", re.I)
_UI_RE = re.compile(r"\bui\b|frontend|component|page|view|form|react|vue|css|html", re.I)
_TEST_RE = re.compile(r"\btest\b|spec|coverage|pytest|jest|vitest", re.I)
_RESEARCH_RE = re.compile(r"research|latest|\bdocs?\b|documentation|changelog|\bversion\b|migrate to latest", re.I)
_DOC_RE = re.compile(r"\bdocs?\b|documentation|readme", re.I)


class TaskPlanner:
    """Deterministic planner: no network, no LLM needed."""

    def plan(self, task: str, language: str = "unknown", framework: str = "none",
             has_tests: bool = False, mode: str = "AUTO") -> TaskProfile:
        t = task.strip()
        tl = t.lower()

        objective = t.split("\n")[0][:280]
        subtasks: List[str] = ["1. inspect project (read-only, no edits)"]
        affected: List[str] = []
        expected: List[str] = []
        tools: List[str] = []
        testing: List[str] = []

        if _AUTH_RE.search(t):
            affected += ["auth"]
            expected += ["auth/*", "tests for auth"]
            subtasks += [
                "2. identify backend + database",
                "3. design auth flow (JWT/session, hashing, validation)",
                "4. implement auth endpoints + middleware",
                "5. add input validation",
                "6. add auth tests",
                "7. run tests",
                "8. repair failures if any",
                "9. final verification",
            ]
        elif _API_RE.search(t):
            affected += ["api"]
            expected += ["api/*", "routes/*"]
            subtasks += [
                "2. identify backend framework",
                "3. design endpoints + schemas",
                "4. implement endpoints",
                "5. add validation + error handling",
                "6. add api tests",
                "7. run tests",
                "8. repair failures if any",
            ]
        elif _DB_RE.search(t):
            affected += ["database"]
            expected += ["models/*", "migrations/*"]
            subtasks += [
                "2. inspect models + migrations",
                "3. design schema change",
                "4. implement change",
                "5. run relevant tests",
                "6. repair failures if any",
            ]
        elif _UI_RE.search(t):
            affected += ["frontend"]
            expected += ["components/*", "pages/*"]
            subtasks += [
                "2. inspect frontend structure",
                "3. implement UI change",
                "4. verify build/typecheck if available",
            ]
        elif (re.search(r"\bbug(s|fix)?\b", tl) or re.search(r"\bfix\b", tl)
              or any(k in tl for k in ("failing", "failed", "failure", "broken", "regression", "stack trace"))):
            affected += ["bugfix"]
            subtasks += [
                "2. reproduce/understand failure",
                "3. locate root cause",
                "4. implement minimal fix",
                "5. run relevant tests",
                "6. verify no regressions",
            ]
        else:
            affected += ["general"]
            subtasks += [
                "2. implement requested change (minimal, scoped)",
                "3. verify with build/tests if available",
            ]

        if _TEST_RE.search(t) or has_tests:
            testing.append(f"{language} tests")
        testing.append("smoke validation (files exist, no obvious runtime error)")

        if "install" in tl or "dependenc" in tl:
            tools.append("package-manager")
        if "git" in tl:
            tools.append("git")
        tools.append("file-edit")
        tools.append("shell")

        if _RESEARCH_RE.search(t) or "internet" in tl or "latest" in tl:
            network_required = True
        else:
            network_required = False

        # complexity / risk heuristics
        if any(k in tl for k in ("system", "architecture", "entire", "migrate", "microservice", "authentication")):
            complexity = "high"
        elif any(k in tl for k in ("feature", "module", "api", "component", "service", "database", "crud")):
            complexity = "medium"
        else:
            complexity = "low"

        if any(k in tl for k in ("delete", "drop", "truncate", "production", "schema", "credential", "secret", "security")):
            risk = "high"
        elif any(k in tl for k in ("modify", "change", "update", "refactor", "rename", "move", "auth")):
            risk = "medium"
        else:
            risk = "low"

        model_requirement = "coder-7b" if complexity in ("medium", "high") else "small"

        return TaskProfile(
            objective=objective,
            subtasks=subtasks,
            affected_areas=sorted(set(affected)),
            expected_files=expected or ["unknown"],
            required_tools=sorted(set(tools)),
            testing_requirements=testing,
            complexity=complexity,
            risk=risk,
            network_required=network_required,
            model_requirement=model_requirement,
            execution_mode=mode,
        )

    def to_dict(self, p: TaskProfile) -> Dict:
        return {
            "objective": p.objective,
            "subtasks": p.subtasks,
            "affected_areas": p.affected_areas,
            "expected_files": p.expected_files,
            "required_tools": p.required_tools,
            "testing_requirements": p.testing_requirements,
            "complexity": p.complexity,
            "risk": p.risk,
            "network_required": p.network_required,
            "model_requirement": p.model_requirement,
            "execution_mode": p.execution_mode,
        }
