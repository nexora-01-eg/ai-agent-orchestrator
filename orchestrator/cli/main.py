"""Main CLI Entry Point"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.cli.commands import CLICommands
from orchestrator.core.config import get_config


def create_parser():
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        prog='agent',
        description='AI Coding Agent Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agent run --project ./my-project --task "Add authentication"
  agent run --project ./my-project --task "Fix bug" --agent OpenCode
  agent run --project ./my-project --task "Build auth" --autonomous --mode AUTONOMOUS
  agent run --project ./my-project --task "Add feature" --multi
  agent analyze --project ./my-project --task "Build auth"
  agent compare --project ./my-project --task "Add feature" --agents OpenCode Aider
  agent list
  agent status
  agent history
  agent doctor
  agent local-models
  agent local-models --coding-only
  agent dashboard --port 8787
  agent schedule list
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # list command
    list_parser = subparsers.add_parser('list', help='List all agents')
    list_parser.set_defaults(func=lambda args: CLICommands().cmd_list(args))

    # status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    status_parser.set_defaults(func=lambda args: CLICommands().cmd_status(args))

    # run command (legacy engine OR supervisor with --autonomous/--mode/--multi)
    run_parser = subparsers.add_parser('run', help='Run a task (add --autonomous for supervisor loop)')
    run_parser.add_argument('--project', '-p', required=True, help='Project path')
    run_parser.add_argument('--task', '-t', required=True, help='Task description')
    run_parser.add_argument('--agent', '-a', help='Agent to use (default: auto)')
    run_parser.add_argument('--model', '-m', help='Model to use')
    run_parser.add_argument('--retries', '-r', type=int, default=3, help='Max retries')
    run_parser.add_argument('--autonomous', action='store_true', help='Run full supervisor loop (Analyze..Validate)')
    run_parser.add_argument('--mode', choices=['SAFE', 'AUTO', 'AUTONOMOUS'], help='Task mode (default from config)')
    run_parser.add_argument('--multi', action='store_true', help='Multi-agent isolated workspaces (no auto-winner)')
    run_parser.set_defaults(func=lambda args: CLICommands().cmd_run(args))

    # analyze command (read-only)
    analyze_parser = subparsers.add_parser('analyze', help='Analyze project + plan task (read-only)')
    analyze_parser.add_argument('--project', '-p', required=True, help='Project path')
    analyze_parser.add_argument('--task', '-t', help='Task description (optional)')
    analyze_parser.set_defaults(func=lambda args: CLICommands().cmd_analyze(args))

    # compare command
    compare_parser = subparsers.add_parser('compare', help='Compare agents on same task')
    compare_parser.add_argument('--project', '-p', required=True, help='Project path')
    compare_parser.add_argument('--task', '-t', required=True, help='Task description')
    compare_parser.add_argument('--agents', nargs='+', help='Agents to compare')
    compare_parser.add_argument('--model', '-m', help='Model to use')
    compare_parser.set_defaults(func=lambda args: CLICommands().cmd_compare(args))

    # history command
    history_parser = subparsers.add_parser('history', help='Show task history')
    history_parser.add_argument('--limit', '-l', type=int, default=20, help='Number of tasks to show')
    history_parser.set_defaults(func=lambda args: CLICommands().cmd_history(args))

    # test command
    test_parser = subparsers.add_parser('test', help='Run tests in project')
    test_parser.add_argument('--project', '-p', required=True, help='Project path')
    test_parser.set_defaults(func=lambda args: CLICommands().cmd_test(args))

    # config command
    config_parser = subparsers.add_parser('config', help='Show configuration')
    config_parser.add_argument('--show', action='store_true', help='Show config')
    config_parser.set_defaults(func=lambda args: CLICommands().cmd_config(args))

    # doctor command
    doctor_parser = subparsers.add_parser('doctor', help='Run system diagnostics')
    doctor_parser.set_defaults(func=lambda args: CLICommands().cmd_doctor(args))

    # local-models command
    models_parser = subparsers.add_parser('local-models', help='List local models')
    models_parser.add_argument('--coding-only', action='store_true', help='Show only coding models')
    models_parser.set_defaults(func=lambda args: CLICommands().cmd_local_models(args))

    # dashboard command (optional)
    dash_parser = subparsers.add_parser('dashboard', help='Start local dashboard (optional)')
    dash_parser.add_argument('--port', type=int, help='Port (default 8787)')
    dash_parser.add_argument('--host', help='Host (default 127.0.0.1)')
    dash_parser.set_defaults(func=lambda args: CLICommands().cmd_dashboard(args))

    # schedule command (stored only, never auto-runs)
    sched_parser = subparsers.add_parser('schedule', help='Manage scheduled tasks (stored only)')
    sched_parser.add_argument('sched_action', nargs='?', default='list', choices=['list', 'add', 'remove', 'run-once'])
    sched_parser.add_argument('--project', '-p', help='Project path (for add)')
    sched_parser.add_argument('--task', '-t', help='Task description (for add)')
    sched_parser.add_argument('--agent', '-a', help='Agent policy (for add)')
    sched_parser.add_argument('--model', '-m', help='Model policy (for add)')
    sched_parser.add_argument('--mode', choices=['SAFE', 'AUTO', 'AUTONOMOUS'], help='Mode (for add)')
    sched_parser.add_argument('--every', choices=['once', 'hourly', 'daily'], help='Schedule (for add)')
    sched_parser.add_argument('--sid', help='Schedule id (for remove/run-once)')
    sched_parser.set_defaults(func=lambda args: CLICommands().cmd_schedule(args))

    return parser


def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        # Initialize config
        get_config()

        # Execute command
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())