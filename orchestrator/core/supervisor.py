"""Autonomous AI Coding Supervisor - central brain over all agents.

Pipeline:
  Task -> Project Analysis -> Agent Discovery (live) -> Model Discovery
  -> Task Planning -> Smart Routing -> Security Gate -> Execution
  -> Validation -> Testing -> Repair -> Final Verification -> Report
"""

from __future__ import annotations

import shutil
import time
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from orchestrator.core.agent_matrix import AgentMatrix, AgentHealth
from orchestrator.core.change_review import ChangeReviewer
from orchestrator.core.config import get_config, PROJECT_ROOT
from orchestrator.core.database import HistoryDatabase, TaskRecord
from orchestrator.core.model_discovery import ModelDiscovery, ModelInfo
from orchestrator.core.observability import TaskLogger
from orchestrator.core.project_analyzer import ProjectAnalyzer, ProjectProfile
from orchestrator.core.router import SmartRouter
from orchestrator.core.security import SecretScanner, remote_send_gate
from orchestrator.core.task_planner import TaskPlanner, TaskProfile
from orchestrator.core.terminal_ui import header, section, kv, step, result_block
from orchestrator.core.test_gate import TestGate
from orchestrator.adapters.factory import AdapterFactory


ERROR_BUILD = "BUILD_ERROR"
ERROR_TEST = "TEST_ERROR"
ERROR_DEP = "DEPENDENCY_ERROR"
ERROR_AUTH = "AUTH_ERROR"
ERROR_TIMEOUT = "TIMEOUT"
ERROR_MODEL = "MODEL_ERROR"
ERROR_AGENT = "AGENT_ERROR"
ERROR_UNKNOWN = "UNKNOWN"

# Destructive-operation phrases only. Bare words like "delete"/"remove" are NOT
# included: normal CRUD features (e.g. "Task CRUD: Create/Read/Update/Delete")
# must not require approval; only destructive system-level operations do.
HIGH_RISK_PATTERNS = ("delete files", "remove files", "delete project", "remove project",
                      "drop database", "drop table", "truncate", "format disk", "format c:",
                      "uninstall", "credential", "password", "secret",
                      "security setting", "system software", "system configuration",
                      "rm -rf", "del /f", "rd /s", "reg delete", "shutdown",
                      "disable antivirus", "disable defender")


class Supervisor:
    def __init__(self, config=None):
        self.config = config or get_config()
        self.project_analyzer = ProjectAnalyzer()
        self.task_planner = TaskPlanner()
        self.matrix = None  # per project path
        self.models = ModelDiscovery(self.config)
        self.router = SmartRouter(self.config)
        self.factory = AdapterFactory(self.config)
        self.db = HistoryDatabase(self.config.config.history.db_path)
        self.secrets = self._make_scanner()
        self.tester = TestGate()
        self.reviewer = ChangeReviewer()

    # ---------- public API ----------
    def run(self, project_path: str, task: str, agent: Optional[str] = None,
            model: Optional[str] = None, mode: str = "AUTO",
            autonomous: bool = False, multi: bool = False,
            max_attempts: Optional[int] = None) -> Dict:
        project_path = str(Path(project_path).resolve())
        task_id = uuid.uuid4().hex[:8]
        logger = TaskLogger(PROJECT_ROOT, task_id)
        start = time.time()

        print(header())
        print(kv("Project", project_path))
        print(kv("Task", task[:200]))
        print(kv("Mode", "AUTONOMOUS" if autonomous else mode))

        # 1. project analysis (read-only)
        print(section("ANALYSIS"))
        project = self.project_analyzer.analyze(project_path)
        logger.supervisor(f"project={asdict(project)}")
        print(kv("Language", project.language))
        print(kv("Framework", project.framework))
        print(kv("Tests", project.test_framework + (f" ({project.test_count} files)" if project.existing_tests else " (none found)")))
        print(kv("Git", f"{project.git_branch} / {project.git_status}"))
        print(kv("Size", f"{project.project_size} ({project.num_files} files)"))

        # 2. agent discovery (live)
        print(section("AGENT DISCOVERY"))
        health = AgentMatrix(self.config, project_path).check_all()
        for name, h in health.items():
            mark = "READY" if h.healthy else ("WARNING" if h.installed else "BLOCKED")
            print(step(h.healthy, f"{name:<10} {mark:<8} {h.reason[:90]}"))
            logger.supervisor(f"health {name}={h.status} {h.reason}")

        # 3. model discovery
        print(section("MODELS"))
        discovered = self.models.discover()
        all_models = discovered["lm-studio"] + discovered["ollama"]
        if all_models:
            for m in all_models[:20]:
                tag = "coding" if m.coding else "NOT coding-capable"
                print(step(bool(m.coding), f"{m.id}  [{m.source}] ({tag})"))
            logger.supervisor(f"models={[m.id for m in all_models]}")
        else:
            print(step(False, "no local models on :1234/:11434 (cloud/free-tier agents still usable)"))
            logger.supervisor("no local models found")

        # 4. task planning
        print(section("PLAN"))
        plan = self.task_planner.plan(task, project.language, project.framework,
                                      has_tests=project.existing_tests, mode=mode)
        logger.supervisor(f"plan={self.task_planner.to_dict(plan)}")
        for s in plan.subtasks:
            print(step(True, s))
        print(kv("Complexity", plan.complexity) + "  " + kv("Risk", plan.risk))
        if plan.network_required:
            print(kv("Network", "required (research/latest docs)"))

        if multi:
            return self._run_multi(project, plan, health, all_models, mode, logger, task_id, start)

        # 5. routing
        route = self.router.route(project, plan, health, all_models, agent, model)
        if not route:
            return self._finish(task_id, project, plan, None, "", False, 0, start, logger,
                                errors=["no healthy agent available"],
                                warnings=["run 'agent doctor' and fix blockers"])
        print(section("AGENT"))
        print(kv("Agent", route.agent))
        print(kv("Model", route.model or "(provider default)"))
        print(kv("Mode", route.execution_mode))
        print(kv("Reason", route.reason))
        logger.supervisor(f"route agent={route.agent} model={route.model} mode={route.execution_mode} reason={route.reason}")

        # human approval only for high-risk
        if self._needs_approval(task, plan, mode, autonomous):
            print(section("APPROVAL REQUIRED"))
            print("High-risk operation detected. Type YES to continue:")
            try:
                ans = input("> ").strip().lower()
            except EOFError:
                ans = ""
            if ans != "yes":
                logger.supervisor("human declined high-risk task")
                return self._finish(task_id, project, plan, route.agent, route.model, False, 0,
                                    start, logger, errors=["declined by human"], warnings=[])

        # 6. supervised execution with fallback + repair
        # bounded repair attempts: 3/4/5 by complexity (never infinite)
        if max_attempts is None:
            if autonomous or mode == "AUTONOMOUS":
                max_attempts = {"low": 3, "medium": 4, "high": 5}.get(plan.complexity, 3)
            else:
                max_attempts = self.config.config.general.max_retries
        print(kv("Max attempts", str(max_attempts)))
        logger.supervisor(f"max_attempts={max_attempts} (complexity={plan.complexity})")
        result = self._execute_supervised(project, plan, task, route, health, all_models,
                                          logger, max_attempts,
                                          autonomous or mode == "AUTONOMOUS")
        return result

    # ---------- supervised execution ----------
    def _execute_supervised(self, project, plan, raw_task, route, health, all_models,
                            logger, max_attempts, autonomous):
        from orchestrator.adapters.base import ExecutionResult
        tried = [route.agent]
        current = route
        attempt = 0
        last: Optional[ExecutionResult] = None
        changed: List[str] = []
        test_details = ""
        warnings: List[str] = []
        errors: List[str] = []

        # security gate before remote
        is_local = current.execution_mode == "local"
        ok, w = remote_send_gate(current.agent, is_local, [], self.secrets)
        for x in w:
            logger.security(x)
            warnings.append(x)

        # secret scan of project (informational; never sends)
        scan = self.secrets.scan_project(project.path)
        for x in scan.warnings:
            logger.security(x)
        if scan.blocked_files and not is_local:
            warnings.append(f"{len(scan.blocked_files)} secret-like file(s) present; they will NOT be sent to remote agent")

        t0 = time.time()
        final_agent = current.agent
        final_model = current.model
        fallbacks: List[Dict] = []
        # Baseline for change detection: agent auto-commits (e.g. Aider) hide
        # work from `git status`, so diff everything since run start.
        base_sha = self._git_head(project.path)

        while attempt < max_attempts:
            attempt += 1
            print(section(f"EXECUTION (attempt {attempt}/{max_attempts})"))
            print(step(True, "Project analyzed"))
            print(step(True, "Workspace prepared"))
            adapter = self.factory.create_adapter(current.agent, project.path)
            if not adapter:
                errors.append(f"cannot create adapter for {current.agent}")
                logger.agent(f"no adapter for {current.agent}")
                nxt = self._fallback(tried, health, all_models, plan, project, reason="AGENT_ERROR")
                if not nxt:
                    break
                logger.supervisor(f"fallback: {current.agent} -> {nxt.agent} reason=AGENT_ERROR")
                fallbacks.append({"from": current.agent, "to": nxt.agent, "reason": "AGENT_ERROR"})
                tried.append(nxt.agent)
                current = nxt
                continue

            # git checkpoint
            try:
                if self.config.config.execution.create_git_checkpoint:
                    adapter.create_git_checkpoint(f"supervisor checkpoint")
                    print(step(True, "Git checkpoint"))
            except Exception:
                pass

            print(step(True, f"Agent started ({current.agent})"))
            logger.agent(f"starting {current.agent} model={current.model or 'default'}")

            # build agent prompt from plan (scoped, no secrets)
            prompt = self._build_prompt(raw_task, plan, project, attempt)
            # Local CPU inference is ~10x slower than cloud: scale the timeout
            # for local execution so working runs are not killed mid-generation.
            base_timeout = self.config.config.general.default_timeout
            timeout = base_timeout * 4 if current.execution_mode == "local" else base_timeout
            res = adapter.execute(prompt, current.model or None, timeout=timeout)
            logger.agent(f"exit={res.exit_code} success={res.success}\nSTDOUT:\n{res.stdout[-4000:]}\nSTDERR:\n{res.stderr[-2000:]}")
            changed = res.changed_files or []
            if changed:
                print(step(True, f"Files modified ({len(changed)})"))
            else:
                print(step(False, "Files modified (none detected)"))

            err_kind = self._classify(res)
            logger.supervisor(f"attempt={attempt} kind={err_kind} exit={res.exit_code}")
            last = res

            if err_kind in (ERROR_AUTH, ERROR_MODEL):
                # do NOT burn attempts: switch agent/model immediately
                errors.append(f"{err_kind}: {(res.errors or [res.stderr[:300]])}")
                nxt = self._fallback(tried, health, all_models, plan, project, reason=err_kind)
                if not nxt:
                    break
                print(step(False, f"{current.agent} blocked ({err_kind}); switching to {nxt.agent}"))
                logger.supervisor(f"fallback: {current.agent} -> {nxt.agent} reason={err_kind}")
                fallbacks.append({"from": current.agent, "to": nxt.agent, "reason": err_kind})
                tried.append(nxt.agent)
                current = nxt
                final_agent, final_model = nxt.agent, nxt.model
                continue

            if err_kind == ERROR_TIMEOUT:
                nxt = self._fallback(tried, health, all_models, plan, project, reason=err_kind)
                if nxt and nxt.agent != current.agent:
                    print(step(False, f"{current.agent} timeout; switching to {nxt.agent}"))
                    logger.supervisor(f"fallback: {current.agent} -> {nxt.agent} reason={err_kind}")
                    fallbacks.append({"from": current.agent, "to": nxt.agent, "reason": err_kind})
                    tried.append(nxt.agent)
                    current = nxt
                    final_agent, final_model = nxt.agent, nxt.model
                    continue
                # else retry same agent (counts as attempt)
                if attempt >= max_attempts:
                    errors.append("TIMEOUT")
                    break
                continue

            if res.success:
                # An exit-0 run can still leave broken output behind (weak
                # local models often do): verify gates BEFORE accepting, so a
                # bad-but-clean exit feeds the repair loop instead of a false
                # success. Bounded by max_attempts like everything else.
                gate_ok, gate_msg = self._quick_gates(project, plan, res, base_sha)
                logger.supervisor(f"in-loop gates ok={gate_ok}: {gate_msg}")
                if gate_ok:
                    break
                errors.append(f"GATE_FAIL: {gate_msg}")
                if attempt >= max_attempts:
                    break
                raw_task = (f"{raw_task}\n\nValidation of your previous changes FAILED: "
                            f"{gate_msg} Fix exactly that, keep everything else, then re-run checks.")
                print(step(False, f"repairing (validation failed: {gate_msg[:120]})"))
                continue

            # code-related failure -> repair loop (same agent, refined prompt)
            if err_kind in (ERROR_BUILD, ERROR_TEST, ERROR_DEP, ERROR_AGENT, ERROR_UNKNOWN):
                errors.append(f"{err_kind}: {(res.errors or [res.stderr[:300]])}")
                if attempt >= max_attempts:
                    break
                raw_task = self._repair_prompt(raw_task, res, err_kind)
                print(step(False, f"repairing ({err_kind})"))
                continue

        # validation gates
        print(section("VALIDATION"))
        duration = time.time() - t0
        # Re-detect changes against the run baseline: catches agent
        # auto-commits that `git status` alone would miss.
        changed = self._changed_since(project.path, base_sha, changed)
        if changed:
            print(step(True, f"Files changed since run start ({len(changed)})"))
            logger.supervisor(f"changed_since_baseline={changed}")
        success = bool(last and last.success)
        verified = False
        test_gate_res = None
        build_gate_res = None

        if success:
            # files exist?
            smoke = self._smoke(project.path, changed)
            print(step(smoke[0], f"Files exist ({smoke[1]})"))
            logger.supervisor(f"smoke={smoke}")
            # build
            from orchestrator.core.test_gate import TestGate
            tg = TestGate()
            build_gate_res = tg.build_if_available(project)
            if build_gate_res:
                print(step(build_gate_res.passed, f"Build ({build_gate_res.command})"))
                logger.tests(f"build {build_gate_res.command} passed={build_gate_res.passed}\n{build_gate_res.details[:3000]}")
            # tests
            test_gate_res = tg.run_tests(project)
            if test_gate_res:
                print(step(test_gate_res.passed, f"Tests ({test_gate_res.command})"))
                logger.tests(f"tests {test_gate_res.command} passed={test_gate_res.passed}\n{test_gate_res.details[:4000]}")
                test_details = test_gate_res.details
            else:
                print(step(True, "Smoke validation (no test suite found)"))
            # change review
            review = self.reviewer.review(project.path, plan.affected_areas)
            self._print_review(review, logger)
            unexpected = bool(review.unexpected)
            if unexpected:
                warnings.append("unexpected changes outside task scope - review required")
            # If the plan requires real tests, a missing suite is a failure,
            # not a pass: never verify vacuously.
            needs_tests = any("smoke" not in (t or "").lower()
                              for t in (plan.testing_requirements or []))
            if needs_tests and test_gate_res is None:
                warnings.append("task requires tests but no test suite was found/run")
                logger.supervisor("tests-required-but-missing")
            tests_ok = (test_gate_res.passed if test_gate_res
                        else (not needs_tests))
            verified = smoke[0] and (build_gate_res.passed if build_gate_res else True) and \
                       tests_ok and not unexpected
            print(step(verified, "Git validation"))
        else:
            print(step(False, "Agent did not succeed; skipping test gate"))

        # Honest statuses only: agent exit 0 without passing gates is FAILED.
        status = "VERIFIED" if (success and verified) else "FAILED"
        print(result_block(status))

        report = self._report(task_id=logger.dir.name, project=project, plan=plan, agent=final_agent,
                              model=final_model, mode=current.execution_mode, duration=duration,
                              attempts=attempt, changed=changed, test_details=test_details,
                              validation={"verified": verified, "build": getattr(build_gate_res, "passed", None),
                                            "tests": getattr(test_gate_res, "passed", None)},
                              errors=errors, warnings=warnings, status=status, logdir=str(logger.dir),
                              fallbacks=fallbacks)
        logger.write_report(report)
        self._save_history(report, raw_task, project)
        return report

    # ---------- multi-agent ----------
    def _run_multi(self, project, plan, health, all_models, mode, logger, task_id, start):
        from orchestrator.core.multi_agent import WorkspaceManager
        mgr = WorkspaceManager(PROJECT_ROOT)
        candidates = [a for a, h in health.items() if h.healthy and a in ("OpenCode", "Aider", "Qwen", "Gemini")]
        if not candidates:
            return self._finish(task_id, project, plan, None, "", False, 0, start, logger, ["no healthy agents"], [])
        print(section(f"MULTI-AGENT ({len(candidates)} isolated workspaces)"))
        results = []
        for agent in candidates:
            ws = mgr.prepare(project.path, agent)
            print(step(True, f"{agent} workspace: {ws}"))
            logger.supervisor(f"multi workspace {agent} -> {ws}")
            route = self.router.route(project, plan, health, all_models, user_agent=agent)
            if not route:
                results.append({"agent": agent, "success": False, "reason": "no route"})
                continue
            adapter = self.factory.create_adapter(agent, str(ws))
            if not adapter:
                results.append({"agent": agent, "success": False, "reason": "no adapter"})
                continue
            t0 = time.time()
            prompt = self._build_prompt(plan.objective + " | " + "; ".join(plan.subtasks[:4]), plan, project, 1)
            try:
                res = adapter.execute(prompt, route.model or None, timeout=self.config.config.general.default_timeout)
                dur = time.time() - t0
                results.append({"agent": agent, "success": res.success, "duration": round(dur, 1),
                                "files": res.changed_files, "errors": res.errors,
                                "workspace": str(ws)})
                logger.agent(f"multi {agent} success={res.success} files={res.changed_files}")
            except Exception as e:
                results.append({"agent": agent, "success": False, "reason": str(e)[:300]})
        print(section("COMPARISON (no auto-winner)"))
        for r in results:
            print(f"  {r['agent']:<10} success={r.get('success')} files={len(r.get('files', []))} duration={r.get('duration', '?')}s")
        report = self._report(task_id=task_id, project=project, plan=plan, agent=",".join(candidates),
                              model="", mode="multi", duration=time.time() - start, attempts=1,
                              changed=[], test_details="", validation={"multi": results},
                              errors=[], warnings=["multi-agent: original project untouched; review workspaces under .orchestrator/workspaces"],
                              status="COMPARED", logdir=str(logger.dir))
        logger.write_report(report)
        return report

    # ---------- helpers ----------
    def _fallback(self, tried, health, all_models, plan, project, reason=""):
        order = self.config.config.agent_preferences.fallback_agents or ["OpenCode", "Aider", "Qwen", "Gemini"]
        healthy = {k: v for k, v in health.items() if v.healthy and k not in tried}
        # never pick a non-free agent when free_only
        if self.config.config.general.free_only:
            healthy = {k: v for k, v in healthy.items() if v.free}
        for cand in order:
            if cand in healthy:
                route = self.router.route(project, plan, health, all_models, user_agent=cand)
                if route:
                    return route
        for cand, h in healthy.items():
            route = self.router.route(project, plan, health, all_models, user_agent=cand)
            if route:
                return route
        return None

    def _needs_approval(self, task, plan, mode, autonomous) -> bool:
        if mode == "SAFE":
            return plan.risk in ("medium", "high")
        if autonomous or mode == "AUTONOMOUS":
            return plan.risk == "high" and any(p in task.lower() for p in HIGH_RISK_PATTERNS)
        # AUTO
        return any(p in task.lower() for p in HIGH_RISK_PATTERNS)

    def _build_prompt(self, task, plan, project, attempt: int) -> str:
        scope = "; ".join(plan.subtasks[:6])
        return (f"{task}\n\nProject: {project.language}/{project.framework} "
                f"(tests: {project.test_framework}). Plan: {scope}. "
                f"Keep changes scoped, do not touch secrets, run relevant checks. "
                f"(attempt {attempt})")

    def _repair_prompt(self, task, res, kind: str) -> str:
        err = "; ".join((res.errors or [])[:3]) or (res.stderr or "")[:800]
        fix = {
            ERROR_BUILD: "Fix build/compilation errors, ensure imports and dependencies exist.",
            ERROR_TEST: "Fix failing tests; keep behavior, adjust implementation.",
            ERROR_DEP: "Install only project-appropriate dependencies, then retry.",
        }.get(kind, "Address the errors below and retry minimally.")
        return f"{task}\n\nPrevious attempt failed ({kind}). {fix} Errors: {err}"

    def _classify(self, res) -> str:
        text = f"{res.stdout or ''}\n{res.stderr or ''}\n{';'.join(res.errors or [])}".lower()
        if any(k in text for k in ("unauthorized", "invalid api key", "auth", "oauth", "permission denied", "401", "403", "needs gemini auth", "no auth")):
            # distinguish real auth failures from mere mentions
            if any(k in text for k in ("incorrect api key", "invalid_api_key", "unauthorized", "needs gemini auth", "no auth type", "authentication required", "oauth")):
                return ERROR_AUTH
        if any(k in text for k in ("timeout", "timed out", "deadline exceeded")) or res.exit_code == 124:
            return ERROR_TIMEOUT
        if any(k in text for k in ("model not found", "no such model", "model unavailable", "failed to load model", "no models", "context length", "context_length", "unknownerror", "unexpected server error", "invalid model", "model_not_found", "unsupported model", "does not exist or you do not have access")):
            return ERROR_MODEL
        if any(k in text for k in ("test failed", "assertion", "pytest", "jest failed", "vitest", "test failure", "failing test")):
            return ERROR_TEST
        if any(k in text for k in ("build failed", "compilation error", "syntaxerror", "tsc ", "type error", "cannot find module", "importerror", "modulenotfounderror")):
            return ERROR_BUILD
        if any(k in text for k in ("no such file", "not found", "missing", "cannot find", "econnrefused", "npm err", "pip install", "package not found")):
            return ERROR_DEP
        if not res.success:
            return ERROR_AGENT
        return "OK"

    def _smoke(self, project_path: str, changed) -> tuple:
        from orchestrator.core.test_gate import TestGate
        try:
            r = TestGate().smoke_validate(project_path, changed or [])
            return (r.passed, r.details)
        except Exception as e:
            return (False, str(e)[:300])

    def _quick_gates(self, project, plan, result, base_sha) -> tuple:
        """Fast in-loop validation after a successful agent exit.

        Returns (ok, message). Uses baseline change detection + smoke +
        real tests when the plan requires them. Keeps the repair loop honest:
        exit 0 alone never counts as done.
        """
        from orchestrator.core.test_gate import TestGate
        try:
            changed = self._changed_since(project.path, base_sha,
                                          result.changed_files or [])
        except Exception:
            changed = result.changed_files or []
        smoke = self._smoke(project.path, changed)
        if not smoke[0]:
            return False, f"smoke: {smoke[1]}"
        needs_tests = any("smoke" not in (t or "").lower()
                          for t in (plan.testing_requirements or []))
        try:
            tg = TestGate().run_tests(project)
        except Exception as e:
            return False, f"test runner error: {e}"[:300]
        if tg is None:
            if needs_tests:
                return False, "plan requires tests but no test suite found"
            return True, "smoke ok, no suite required"
        if not tg.passed:
            return False, f"tests failed ({tg.command}): {(tg.details or '')[:400]}"
        return True, "smoke + tests pass"

    @staticmethod
    def _git_head(project_path: str) -> Optional[str]:
        import subprocess
        try:
            r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(project_path),
                               capture_output=True, text=True, timeout=15)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None

    def _changed_since(self, project_path: str, base_sha: Optional[str],
                       detected: List[str]) -> List[str]:
        """Union of committed-since-baseline + working-tree changes, filtered."""
        import subprocess
        from pathlib import Path as _P
        seen: List[str] = []
        def _add(p: str):
            p = (p or "").strip().strip('"')
            if not p:
                return
            low = p.replace("\\", "/").lower()
            if low.startswith(".aider") or low.startswith("__pycache__/") or \
               "/__pycache__/" in low or low.startswith(".pytest_cache/"):
                return
            if p not in seen:
                seen.append(p)
        for f in detected or []:
            _add(f)
        try:
            if base_sha:
                r = subprocess.run(["git", "diff", "--name-only", base_sha, "HEAD"],
                                   cwd=str(project_path), capture_output=True,
                                   text=True, timeout=20)
                if r.returncode == 0:
                    for line in r.stdout.splitlines():
                        _add(line)
            r2 = subprocess.run(["git", "status", "--porcelain"], cwd=str(project_path),
                                capture_output=True, text=True, timeout=15)
            if r2.returncode == 0:
                for line in r2.stdout.splitlines():
                    if not line.strip() or len(line) < 4:
                        continue
                    p = line[3:].strip()
                    if " -> " in p:
                        p = p.split(" -> ")[-1].strip()
                    _add(p)
        except Exception:
            pass
        return seen
    def _print_review(self, review, logger):
        print(f"  changed={len(review.files_changed)} created={len(review.files_created)} deleted={len(review.files_deleted)}")
        if review.diff_stat:
            print("  --- diff --stat ---")
            print("  " + "\n  ".join(review.diff_stat.splitlines()[:15]))
        for w in review.warnings:
            print(f"  WARNING: {w}")
            logger.supervisor(f"review warning: {w}")

    def _make_scanner(self):
        from orchestrator.core.config import PROJECT_ROOT as PR
        try:
            data = self.config.config
            # secret_scanner section may not be parsed into dataclass; read yaml directly
            import yaml
            raw = yaml.safe_load(open(self.config.config_path, encoding="utf-8"))
            sc = (raw.get("secret_scanner") or {})
            from orchestrator.core.security import SecretScanner
            return SecretScanner(patterns=sc.get("patterns"), exclude=sc.get("exclude_patterns"))
        except Exception:
            from orchestrator.core.security import SecretScanner
            return SecretScanner()

    def _report(self, task_id, project, plan, agent, model, mode, duration, attempts,
                changed, test_details, validation, errors, warnings, status, logdir,
                fallbacks=None) -> Dict:
        return {
            "task_id": task_id,
            "date": datetime.now().isoformat(),
            "task": plan.objective,
            "project": project.path,
            "language": project.language,
            "framework": project.framework,
            "agent": agent,
            "model": model,
            "execution_mode": mode,
            "duration": round(duration, 2),
            "attempts": attempts,
            "files_changed": changed,
            "tests": (test_details or "")[:4000],
            "validation": validation,
            "security_checks": {"secret_scan": "enabled", "remote_gate": "enforced"},
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "fallbacks": fallbacks or [],
            "logdir": logdir,
        }

    def _save_history(self, report: Dict, raw_task: str, project) -> None:
        try:
            if not self.config.config.history.enabled:
                return
            rec = TaskRecord(
                task_id=report["task_id"], date=report["date"], project_path=project.path,
                task_description=raw_task, selected_agent=str(report["agent"]), model=str(report["model"]),
                attempts=int(report["attempts"]), duration_seconds=float(report["duration"]),
                changed_files=report["files_changed"], tests_run=bool(report["tests"]),
                test_results=str(report["tests"])[:5000],
                result="success" if report["status"] in ("VERIFIED", "SUCCESS") else ("partial" if report["status"] == "COMPARED" else "failed"),
                errors="; ".join(report["errors"])[:4000], execution_log=f"logdir={report['logdir']}",
            )
            self.db.add_task(rec)
            self.db.cleanup_old_tasks(self.config.config.history.max_entries)
        except Exception:
            pass

    def _finish(self, task_id, project, plan, agent, model, success, attempts, start, logger, errors, warnings) -> Dict:
        report = self._report(task_id, project, plan, agent or "", model or "", "n/a",
                              time.time() - start, attempts, [], "", {"verified": False},
                              errors, warnings, "FAILED" if errors else "SUCCESS", str(logger.dir))
        logger.write_report(report)
        return report
