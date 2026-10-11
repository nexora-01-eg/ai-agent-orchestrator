# AI Coding Supervisor (over Agent Orchestrator)

A Windows-based **autonomous supervisor** managing multiple AI coding agents
(OpenCode, Aider, Gemini CLI, Qwen Code) with local model support via LM Studio.
The supervisor plans, routes, executes, validates, tests, repairs and reports.
See `SUPERVISOR.md` for the full pipeline.

## Features

- **Supervisor Brain**: project analysis, task planning, smart routing, validation gates
- **Multi-Agent Management**: Unified interface for OpenCode, Aider, Gemini CLI, and Qwen Code
- **Live Health Checks**: READY/WARNING/BLOCKED per agent before every task
- **Local-First + Free-Only**: local models preferred; paid APIs forbidden by default
- **Secret Protection**: secret scanner + remote-send gate + log redaction
- **Git Safety**: Automatic git checkpoints before changes, change review after
- **Repair Loop**: error classification (BUILD/TEST/DEPENDENCY/AUTH/TIMEOUT/MODEL) with fallback
- **Test Gate**: build + tests must pass for VERIFIED status (else SUCCESS/FAILED, honestly reported)
- **Multi-Agent Mode**: isolated workspaces per agent, comparison table, no auto-winner
- **Observability**: structured logs per task under `logs/YYYY-MM-DD/<task-id>/` + SQLite history
- **Optional Dashboard**: local `http://localhost:8787` (CLI works without it)
- **Scheduler**: stored tasks only, never auto-runs
- **Plugin Agents**: drop `orchestrator/agents/<name>.py` to add an agent, no core changes
- **Windows Integration**: Batch launchers for easy access
- **Configuration**: YAML-based configuration

## Quick Start

### Prerequisites

- Windows 10/11
- Python 3.11+
- Node.js 18+
- Git
- Installed agents: OpenCode, Aider, Gemini CLI, Qwen Code

### Installation

```cmd
cd C:\Users\NOUR SOFT\Documents\AI-Agent-Orchestrator
run-agent.bat doctor
```

### Running a Task

```cmd
# Using the menu
agent-menu.bat

# Supervised run (recommended)
run-agent.bat run --project "C:\path\to\project" --task "Create a REST API with authentication" --mode AUTO

# Full autonomous loop
run-agent.bat run --project "C:\path\to\project" --task "Fix failing tests" --autonomous

# Multi-agent comparison (isolated workspaces)
run-agent.bat run --project "C:\path\to\project" --task "Add validation" --multi

# Read-only analysis + plan (never edits)
run-agent.bat analyze --project "C:\path\to\project" --task "Build auth system"

# With specific agent (only if currently healthy)
run-agent.bat run --project "C:\path\to\project" --task "Fix bug in login" --agent OpenCode
```

## Commands

| Command | Description |
|---------|-------------|
| `list` | List all agents and their status |
| `status` | Show system status |
| `run` | Supervised task run (`--mode SAFE/AUTO/AUTONOMOUS`, `--autonomous`, `--multi`) |
| `analyze` | Read-only project analysis + task plan |
| `compare` | Compare agents on same task (legacy engine) |
| `history` | Show task history |
| `test` | Run tests in project |
| `config` | Show configuration |
| `doctor` | Live health matrix (READY/WARNING/BLOCKED) |
| `local-models` | Live local model discovery |
| `dashboard` | Start optional local dashboard (`:8787`) |
| `schedule` | Manage stored scheduled tasks |

## Configuration

Edit `config.yaml` to customize:

- Agent preferences
- Local model server settings
- Execution settings
- Testing commands
- Safety rules
- History database

## Project Structure

```
AI-Agent-Orchestrator/
├── agent_orchestrator.py      # Main entry point
├── config.yaml                # Configuration
├── agents.json                # Discovered agent capabilities
├── run-agent.bat              # Windows CLI launcher
├── doctor.bat                 # Windows diagnostics launcher
├── agent-menu.bat             # Interactive menu
├── Fix-Python-Path.ps1        # Python PATH fix (run as Admin)
├── orchestrator/
│   ├── core/
│   │   ├── config.py         # Configuration management
│   │   ├── database.py       # SQLite history database
│   │   ├── analyzer.py       # Task analysis & agent selection
│   │   └── engine.py         # Execution engine with retry
│   ├── adapters/
│   │   ├── base.py           # Base adapter interface
│   │   ├── opencode.py       # OpenCode adapter
│   │   ├── aider.py          # Aider adapter
│   │   ├── gemini.py         # Gemini CLI adapter
│   │   ├── qwen.py           # Qwen Code adapter
│   │   ├── lmstudio.py       # LM Studio adapter
│   │   └── factory.py        # Adapter factory
│   └── cli/
│       ├── main.py           # CLI entry point
│       └── commands.py       # Command implementations
└── workspaces/               # Task workspaces
```

## Local Models with LM Studio

1. Install LM Studio from https://lmstudio.ai
2. Download a coding model (e.g., qwen2.5-coder-7b-instruct)
3. Start the server on port 1234
4. Configure in `config.yaml`:
   ```yaml
   local_models:
     lm_studio:
       enabled: true
       url: "http://localhost:1234/v1"
       api_key: "lm-studio"
   ```

## Adding New Agents

1. Create a new adapter in `orchestrator/adapters/` inheriting from `BaseAgentAdapter`
2. Register in `orchestrator/adapters/factory.py`
3. Add configuration to `config.yaml`

## Safety Features

- Git checkpoints before changes
- Blocked commands/paths
- Confirmation for destructive operations
- No automatic git push
- No credential handling

## License

MIT License