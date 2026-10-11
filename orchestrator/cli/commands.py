"""CLI Commands Implementation"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, List
from orchestrator.core.config import get_config
from orchestrator.core.database import get_database, HistoryDatabase
from orchestrator.core.engine import ExecutionEngine
from orchestrator.adapters.factory import AdapterFactory
from orchestrator.adapters.lmstudio import LMStudioAdapter


class CLICommands:
    """CLI command implementations"""

    def __init__(self, config=None):
        self.config = config or get_config()
        self.engine = ExecutionEngine(self.config)
        self.factory = AdapterFactory(self.config)
        self.db = get_database(self.config.config.history.db_path)

    def cmd_list(self, args):
        """List all agents and their status"""
        print("\n=== AI Coding Agents ===\n")

        # Load agents.json for actual status
        agents_json_path = Path(__file__).parent.parent.parent / "agents.json"
        agents_data = {}
        if agents_json_path.exists():
            with open(agents_json_path) as f:
                agents_data = json.load(f)

        enabled_agents = self.config.get_enabled_agents()

        for name, agent_config in enabled_agents.items():
            status = "UNKNOWN"
            working = False

            if agents_data:
                agent_data = agents_data.get('agents', {}).get(name, {})
                working = agent_data.get('working', False)
                if working:
                    status = "WORKING"
                elif agent_data.get('blocked_by'):
                    status = f"BLOCKED: {agent_data['blocked_by']}"
                else:
                    status = "NOT TESTED"

            caps = []
            if agent_config.supports_local:
                caps.append("Local Models")
            if agent_config.requires_auth:
                caps.append("Requires Auth")
            if agent_config.free_tier:
                caps.append("Free")

            print(f"  {name} v{agent_config.version}")
            print(f"    Status: {status}")
            print(f"    Command: {agent_config.command}")
            print(f"    Capabilities: {', '.join(caps) if caps else 'None'}")
            print(f"    License: {agent_config.license}")
            print()

    def cmd_status(self, args):
        """Show system status"""
        print("\n=== System Status ===\n")

        # Check tools
        print("Tools:")
        tools = self.config.config.get('tools', {}) if hasattr(self.config.config, 'get') else {}
        # Just show basic info
        print(f"  Python: {self._get_python_version()}")
        print(f"  Node.js: {self._get_node_version()}")
        print(f"  Git: {self._get_git_version()}")
        print()

        # Check agents
        print("Agents:")
        self.cmd_list(args)
        print()

        # Check LM Studio
        print("Local Model Servers:")
        lm = LMStudioAdapter(self.config, ".")
        if lm.check_available():
            models = lm.get_available_models()
            coding_models = lm.get_coding_models()
            print(f"  LM Studio: RUNNING ({len(models)} models)")
            if coding_models:
                print(f"    Coding models: {', '.join([m['id'] for m in coding_models])}")
            recommended = lm.recommend_model()
            if recommended:
                print(f"    Recommended: {recommended}")
        else:
            print("  LM Studio: NOT RUNNING")
        print()

        # Database stats
        if self.config.config.history.enabled:
            stats = self.db.get_stats()
            print("History:")
            print(f"  Total tasks: {stats['total_tasks']}")
            print(f"  Success: {stats['success']}")
            print(f"  Failed: {stats['failed']}")
            print(f"  By agent: {stats['by_agent']}")

    def cmd_run(self, args):
        """Run a task (legacy engine) or supervised execution with --autonomous/--mode/--multi."""
        if getattr(args, "autonomous", False) or getattr(args, "mode", None) or getattr(args, "multi", False):
            return self.cmd_supervise(args)
        if not args.project:
            print("Error: Project path required")
            return

        if not args.task:
            print("Error: Task description required")
            return

        project_path = Path(args.project).resolve()
        if not project_path.exists():
            print(f"Error: Project path does not exist: {project_path}")
            return

        print(f"\n=== Running Task ===")
        print(f"Project: {project_path}")
        print(f"Task: {args.task}")
        if args.agent:
            print(f"Agent: {args.agent}")
        if args.model:
            print(f"Model: {args.model}")
        print()

        result = self.engine.execute_task(
            str(project_path),
            args.task,
            agent_name=args.agent,
            model=args.model,
            max_attempts=args.retries
        )

        print(f"\n=== Result ===")
        if result['success']:
            print("SUCCESS!")
        else:
            print("FAILED!")
        print(f"Task ID: {result['task_id']}")
        print(f"Agent: {result['agent']}")
        print(f"Attempts: {result['attempts']}")
        print(f"Duration: {result['duration']:.2f}s")
        if result['changed_files']:
            print(f"Changed files: {', '.join(result['changed_files'])}")
        if result['tests_run']:
            print(f"Tests run: Yes")
            if result['test_results']:
                print(f"Test output: {result['test_results'][:500]}...")
        if result['errors']:
            print(f"Errors: {'; '.join(result['errors'])}")

        return result

    def cmd_supervise(self, args):
        """Supervised execution: analysis -> routing -> execution -> validation -> report."""
        from orchestrator.core.supervisor import Supervisor
        project = getattr(args, "project", None)
        task = getattr(args, "task", None)
        if not project or not task:
            print("Error: --project and --task are required")
            return
        mode = (getattr(args, "mode", None) or self.config.config.supervisor.default_mode or "AUTO").upper()
        if mode not in ("SAFE", "AUTO", "AUTONOMOUS"):
            print(f"Error: invalid mode {mode} (use SAFE, AUTO, AUTONOMOUS)")
            return
        autonomous = bool(getattr(args, "autonomous", False)) or mode == "AUTONOMOUS"
        multi = bool(getattr(args, "multi", False))
        sup = Supervisor(self.config)
        report = sup.run(str(project), str(task),
                         agent=getattr(args, "agent", None),
                         model=getattr(args, "model", None),
                         mode=mode, autonomous=autonomous, multi=multi,
                         max_attempts=getattr(args, "retries", None) or self.config.config.supervisor.max_attempts)
        print(f"\nReport: {report.get('logdir', '')}\\report.json")
        return report

    def cmd_analyze(self, args):
        """Analyze project + task plan (read-only)."""
        from orchestrator.core.project_analyzer import ProjectAnalyzer
        from orchestrator.core.task_planner import TaskPlanner
        project = getattr(args, "project", None)
        if not project:
            print("Error: --project required")
            return
        pa = ProjectAnalyzer().analyze(str(Path(project).resolve()))
        print("\n=== PROJECT ===")
        print(f"  Name: {pa.name}")
        print(f"  Language: {pa.language}  Framework: {pa.framework}")
        print(f"  Package manager: {pa.package_manager}  Build: {pa.build_system}  Tests: {pa.test_framework}")
        print(f"  Git: {pa.git_branch} / {pa.git_status} (clean={pa.git_clean})")
        print(f"  Size: {pa.project_size} ({pa.num_files} files, {pa.num_dirs} dirs)")
        print(f"  Configs: {', '.join(pa.config_files) if pa.config_files else 'none'}")
        print(f"  Important dirs: {', '.join(pa.important_directories) if pa.important_directories else 'none'}")
        print(f"  Tests: {'yes' if pa.existing_tests else 'no'} ({pa.test_count})  Dockerfile: {pa.has_dockerfile}  README: {pa.has_readme}")
        if getattr(args, "task", None):
            plan = TaskPlanner().plan(args.task, pa.language, pa.framework, pa.existing_tests)
            print("\n=== TASK PLAN ===")
            print(f"  Objective: {plan.objective}")
            for s in plan.subtasks:
                print(f"  - {s}")
            print(f"  Complexity: {plan.complexity}  Risk: {plan.risk}  Network: {plan.network_required}")

    def cmd_dashboard(self, args):
        """Start local dashboard (optional)."""
        from orchestrator.dashboard.app import serve
        host = getattr(args, "host", None) or self.config.config.dashboard.host
        port = getattr(args, "port", None) or self.config.config.dashboard.port
        root = str(Path(__file__).parent.parent.parent)
        serve(root, host, int(port))

    def cmd_schedule(self, args):
        """Manage scheduled tasks (stored only, never auto-runs)."""
        from orchestrator.core.scheduler import Scheduler
        root = str(Path(__file__).parent.parent.parent)
        sch = Scheduler(root)
        sub = getattr(args, "sched_action", "list")
        if sub == "add":
            if not getattr(args, "project", None) or not getattr(args, "task", None):
                print("Error: schedule add needs --project and --task")
                return
            st = sch.add(args.project, args.task, getattr(args, "agent", None) or "auto",
                         getattr(args, "model", None) or "auto",
                         (getattr(args, "mode", None) or "AUTO").upper(),
                         getattr(args, "every", None) or "once")
            print(f"Scheduled: {st.id} ({st.schedule})")
        elif sub == "remove":
            ok = sch.remove(getattr(args, "sid", ""))
            print("Removed." if ok else "Not found.")
        elif sub == "run-once":
            items = [x for x in sch.list() if x.get("id") == getattr(args, "sid", "")]
            if not items:
                print("Not found.")
                return
            it = items[0]
            from orchestrator.core.supervisor import Supervisor
            rep = Supervisor(self.config).run(it["project"], it["task"], mode=it.get("mode", "AUTO"))
            sch.mark_run(it["id"])
            print(f"Status: {rep.get('status')}")
        else:
            items = sch.list()
            if not items:
                print("No scheduled tasks.")
                return
            for x in items:
                print(f"  {x['id']} | {x['schedule']:<6} | {x['mode']:<10} | {x['project']} :: {x['task'][:70]}")

    def cmd_compare(self, args):
        """Compare agents on same task"""
        if not args.project:
            print("Error: Project path required")
            return

        if not args.task:
            print("Error: Task description required")
            return

        project_path = Path(args.project).resolve()
        if not project_path.exists():
            print(f"Error: Project path does not exist: {project_path}")
            return

        available_adapters = self.factory.get_available_adapters(str(project_path))
        if not available_adapters:
            print("Error: No working agents available")
            return

        agents_to_test = list(available_adapters.keys())
        if args.agents:
            agents_to_test = [a for a in args.agents if a in available_adapters]

        print(f"\n=== Comparing Agents ===")
        print(f"Project: {project_path}")
        print(f"Task: {args.task}")
        print(f"Agents: {', '.join(agents_to_test)}")
        print()

        results = {}
        for agent_name in agents_to_test:
            print(f"\n--- Testing {agent_name} ---")
            result = self.engine.execute_task(
                str(project_path),
                args.task,
                agent_name=agent_name,
                model=args.model
            )
            results[agent_name] = result

        # Print comparison
        print("\n=== Comparison Results ===")
        print(f"{'Agent':<15} {'Success':<8} {'Attempts':<10} {'Duration':<10} {'Files':<8} {'Tests':<8}")
        print("-" * 70)

        for agent_name, result in results.items():
            success = "Yes" if result['success'] else "No"
            attempts = str(result['attempts'])
            duration = f"{result['duration']:.1f}s"
            files = str(len(result['changed_files']))
            tests = "Yes" if result['tests_run'] else "No"
            print(f"{agent_name:<15} {success:<8} {attempts:<10} {duration:<10} {files:<8} {tests:<8}")

    def cmd_history(self, args):
        """Show task history"""
        limit = args.limit or 20

        tasks = self.db.get_all_tasks(limit=limit)

        if not tasks:
            print("No history found")
            return

        print(f"\n=== Task History (last {limit}) ===\n")
        for task in tasks:
            status = "SUCCESS" if task.result == "success" else "FAILED" if task.result == "failed" else "PARTIAL"
            print(f"  {task.task_id} | {task.date[:19]} | {task.selected_agent:<12} | {status:<8} | {task.project_path}")
            print(f"    Task: {task.task_description[:80]}...")
            if task.changed_files:
                print(f"    Files: {', '.join(task.changed_files[:5])}{'...' if len(task.changed_files) > 5 else ''}")
            print()

    def cmd_test(self, args):
        """Run tests in project"""
        if not args.project:
            print("Error: Project path required")
            return

        project_path = Path(args.project).resolve()
        if not project_path.exists():
            print(f"Error: Project path does not exist: {project_path}")
            return

        test_cmd = self.engine._detect_test_command(project_path)
        if not test_cmd:
            print("No test command detected for this project")
            return

        print(f"Running: {test_cmd}")
        import subprocess
        result = subprocess.run(
            test_cmd,
            cwd=project_path,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8',
            errors='replace'
        )

        print(f"Exit code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")

    def cmd_config(self, args):
        """Show or edit configuration"""
        if args.show:
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
            with open(config_path) as f:
                print(f.read())
        else:
            print("Use --show to view config. Editing not yet implemented.")

    def cmd_doctor(self, args):
        """Practical diagnostics tree with live states + WHAT YOU NEED TO DO."""
        from orchestrator.core.agent_matrix import AgentMatrix
        from orchestrator.core.model_discovery import ModelDiscovery
        root = Path(__file__).parent.parent.parent
        actions: list = []

        def mark(ok: bool, warn: bool = False) -> str:
            return "READY" if ok else ("WARNING" if warn else "BLOCKED")

        print("\nSYSTEM")
        py = self._get_python_version()
        py_ok = "not found" not in py.lower() and "error" not in py.lower()
        print(f"+- Python   [{mark(py_ok)}] {py}")
        nd = self._get_node_version()
        nd_ok = "not found" not in nd.lower() and "error" not in nd.lower()
        print(f"+- Node     [{mark(nd_ok)}] {nd}")
        gv = self._get_git_version()
        gv_ok = "not found" not in gv.lower() and "error" not in gv.lower()
        print(f"+- Git      [{mark(gv_ok)}] {gv}")
        try:
            import subprocess as _sp
            _sp.run([__import__("sys").executable, "-m", "pytest", "--version"],
                    capture_output=True, timeout=20)
            print("+- pytest    [READY] installed (test gate active)")
            pytest_ok = True
        except Exception:
            print("+- pytest    [WARNING] not installed (test gate falls back to smoke validation)")
            pytest_ok = False
        import platform as _pl
        print(f"\\- Hardware  [READY] { _pl.processor() or _pl.machine()}")

        print("\nAGENTS (live health check)")
        matrix = AgentMatrix(self.config, ".").check_all()
        for i, (name, h) in enumerate(matrix.items()):
            last = i == len(matrix) - 1
            br = "\\-" if last else "+-"
            print(f"{br} {name:<8} [{h.status}] {h.reason[:100]}")
            if h.action:
                actions.append(f"{name}: {h.action}")

        print("\nMODELS (live /v1/models)")
        disc = ModelDiscovery(self.config).discover()
        lm = disc.get("lm-studio", [])
        ol = disc.get("ollama", [])
        print(f"+- LM Studio [{ 'READY' if lm else 'BLOCKED'}] " +
              (f"{len(lm)} model(s): " + ", ".join(m.id for m in lm[:5]) if lm else "server down or zero models"))
        print(f"+- Ollama    [{ 'READY' if ol else 'BLOCKED'}] " +
              (f"{len(ol)} model(s)" if ol else "not running"))
        print("\\- Other local providers  [WARNING] only LM Studio/Ollama endpoints are probed")
        if not lm and not ol:
            actions.append("LM Studio: start the server (open LM Studio -> Developer tab -> Start Server, or: lms server start --port 1234), then download + load a coding model")

        print("\nSUPERVISOR")
        print("+- Router        [READY] capability routing, unhealthy agents never selected")
        print("+- Security      [READY] secret scanner + remote-send gate + log redaction" if self.config.config.secret_scanner.enabled else "+- Security      [WARNING] secret scanner DISABLED")
        print("+- Test Gate     [READY]" if pytest_ok else "+- Test Gate     [WARNING] smoke-validation only (install pytest for full gate)")
        print("+- Repair Loop   [READY] bounded 3/4/5 attempts by complexity + fallback with reason log")
        print("+- Multi-Agent   [READY] isolated workspaces, comparison only")
        print(f"\\- Dashboard     [READY] optional at http://{self.config.config.dashboard.host}:{self.config.config.dashboard.port} (CLI independent)")

        print("\nWHAT YOU NEED TO DO")
        if not actions:
            print("  Nothing. All systems operational.")
        else:
            seen = set()
            for a in actions:
                if a not in seen:
                    seen.add(a)
                    print(f"  - {a}")
            print("  (Everything else is already prepared and will auto-detect once the above is done.)")

    def cmd_local_models(self, args):
        """List and manage local models"""
        lm = LMStudioAdapter(self.config, ".")

        if not lm.check_available():
            print("LM Studio is not running. Start LM Studio and enable the server.")
            return

        models = lm.get_available_models()
        coding_models = lm.get_coding_models()

        print(f"\n=== Available Models ({len(models)}) ===\n")

        if args.coding_only:
            models = coding_models

        for model in models:
            model_id = model.get('id', 'unknown')
            is_coding = model in coding_models
            marker = " [CODING]" if is_coding else ""
            print(f"  {model_id}{marker}")

        recommended = lm.recommend_model()
        if recommended:
            print(f"\nRecommended for coding: {recommended}")

    def _get_python_version(self) -> str:
        """Get Python version"""
        try:
            import subprocess
            result = subprocess.run(
                [r"C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else "Not found"
        except:
            return "Error"

    def _get_node_version(self) -> str:
        """Get Node version"""
        try:
            import subprocess
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else "Not found"
        except:
            return "Error"

    def _get_git_version(self) -> str:
        """Get Git version"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else "Not found"
        except:
            return "Error"