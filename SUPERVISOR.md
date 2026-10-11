# Autonomous AI Coding Supervisor

The Supervisor is the central brain over all agents. It never edits code itself;
it plans, routes, executes via adapters, validates, repairs, and reports.

## Pipeline

```
Task
 -> Project Analysis (read-only)
 -> Agent Discovery (live health check, never blind trust)
 -> Model Discovery (GET /v1/models, never invented names)
 -> Task Planning (objective + subtasks)
 -> Smart Routing (descriptive reason, no score display)
 -> Security Gate (secret scan + remote-send gate + redaction)
 -> Execution (git checkpoint first)
 -> Validation (files exist)
 -> Test Gate (build + tests, or smoke validation)
 -> Repair Loop (code errors only, max 3 attempts)
 -> Change Review (diff summary, unexpected-change warnings)
 -> Final Report (report.json + SQLite history)
```

## Task Modes

| Mode | Behavior |
|------|----------|
| `SAFE` | Asks approval for medium/high-risk tasks |
| `AUTO` | Automatic inside project workspace; approval only for high-risk destructive patterns |
| `AUTONOMOUS` | Full Analyze->Validate loop; still never bypasses Security Gates |

Even AUTONOMOUS never: pushes git, touches secrets, disables security,
installs system software, or uses paid APIs when `free_only: true`.

## Commands

```cmd
:: supervised single-agent run
run-agent.bat run --project "C:\path\to\proj" --task "Add JWT auth" --mode AUTO

:: full autonomous loop
run-agent.bat run --project "C:\path\to\proj" --task "Fix failing tests" --autonomous

:: multi-agent (isolated workspaces, comparison only, no auto-winner)
run-agent.bat run --project "C:\path\to\proj" --task "Add validation" --multi

:: read-only analysis + plan (never edits)
run-agent.bat analyze --project "C:\path\to\proj" --task "Build auth system"

:: live health matrix
run-agent.bat doctor

:: local models (live discovery)
run-agent.bat local-models --coding-only

:: dashboard (optional)
run-agent.bat dashboard --port 8787

:: scheduler (stored only, never auto-runs)
run-agent.bat schedule list
run-agent.bat schedule add --project "C:\p" --task "Nightly tests" --every daily
run-agent.bat schedule run-once --sid <id>
run-agent.bat schedule remove --sid <id>
```

## Routing Logic

1. If you name an `--agent`, it is used only when currently healthy;
   otherwise the run fails fast with the blocker reason (no silent fallback
   on explicit choice).
2. Local/private tasks + local models available -> local agent
   (OpenCode general, Aider git-heavy, Qwen complex orchestration).
3. Research/network tasks -> authenticated remote-free agent (Gemini).
4. Auth/model/timeout failures -> automatic fallback to next healthy agent
   without burning attempts. Code failures -> repair loop on same agent.

## Statuses

- `VERIFIED` - agent succeeded AND files exist AND build/tests pass AND no unexpected changes
- `SUCCESS` - agent succeeded but some gate did not pass (see report for which)
- `FAILED` - agent failed or no healthy agent
- `COMPARED` - multi-agent comparison finished (original untouched)

## Observability

Every run writes to `logs/YYYY-MM-DD/<task-id>/`:

- `supervisor.log` - routing, gates, validation
- `agent.log` - raw agent stdout/stderr (secrets redacted)
- `tests.log` - build/test output
- `security.log` - secret scan + remote-gate decisions
- `report.json` - final machine-readable report

SQLite history (`orchestrator.db`) keeps task summaries.

## Adding a New Agent (plugin)

Create `orchestrator/agents/<name>.py`:

```python
from orchestrator.adapters.base import BaseAgentAdapter, AgentCapabilities, ExecutionResult

ADAPTER_NAME = "MyAgent"

class MyAgentAdapter(BaseAgentAdapter):
    @property
    def agent_name(self): return "MyAgent"
    def get_capabilities(self): return AgentCapabilities(file_read=True, ...)
    def check_available(self): ...
    def prepare_command(self, task, model=None, **kw): ...
    def parse_output(self, stdout, stderr, exit_code=0): ...

ADAPTER_CLASS = MyAgentAdapter
```

Then `agent doctor` discovers it automatically. No core changes needed.

## Cost / Privacy Policy

Defaults in `config.yaml`:

```yaml
general:
  free_only: true
  local_first: true
supervisor:
  cost_policy: "ZERO_COST"
```

- `free_only: true` forbids paid APIs/models/subscriptions.
- `local_first: true` prefers local models; project code is never sent
  to the internet when a local model can do the task.
- Remote agents never receive secret-like files (`.env`, keys, tokens)
  without explicit human approval; logs are redacted.
