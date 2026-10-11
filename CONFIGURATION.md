# Configuration Guide

## Configuration File

The main configuration file is `config.yaml` in the project root. All settings can be modified without changing source code.

## Configuration Sections

### General Settings

```yaml
general:
  workspace_dir: "C:\\Users\\NOUR SOFT\\Documents\\AI-Agent-Orchestrator\\workspaces"
  log_level: "INFO"              # DEBUG, INFO, WARN, ERROR
  max_retries: 3                 # Max retry attempts for failed tasks
  default_timeout: 300           # Default timeout in seconds
  auto_approve: false            # Auto-approve all actions (dangerous!)
  confirm_destructive: true      # Confirm before destructive operations
```

### Agent Preferences

```yaml
agent_preferences:
  default_agent: "auto"          # auto, OpenCode, Aider, Gemini, Qwen
  fallback_agents: ["OpenCode", "Aider", "Qwen", "Gemini"]
  prefer_local_models: true      # Prefer agents with local model support
```

### Local Model Servers

```yaml
local_models:
  lm_studio:
    enabled: true
    url: "http://localhost:1234/v1"
    api_key: "lm-studio"
  ollama:
    enabled: false
    url: "http://localhost:11434/v1"
    api_key: ""
```

### Agent-Specific Configurations

Each agent has its own configuration section:

#### OpenCode
```yaml
OpenCode:
  enabled: true
  command: "opencode"
  path: "C:\\Users\\NOUR SOFT\\AppData\\Roaming\\npm\\opencode.ps1"
  args: []
  env: {}
  supports_local: true
  local_model_config:
    provider: "openai_compatible"
    base_url: "http://localhost:1234/v1"
    api_key: "lm-studio"
    model: "qwen2.5-coder-7b-instruct"
```

#### Aider
```yaml
Aider:
  enabled: true
  command: "aider"
  args: ["--yes-always", "--no-gitignore"]
  env:
    OLLAMA_API_BASE: "http://localhost:1234/v1"
  supports_local: true
  local_model_config:
    model: "openai/qwen2.5-coder-7b-instruct"
    openai_base_url: "http://localhost:1234/v1"
    openai_api_key: "lm-studio"
```

#### Gemini
```yaml
Gemini:
  enabled: true
  command: "gemini"
  args: []
  env: {}
  supports_local: false
  requires_auth: true
```

#### Qwen
```yaml
Qwen:
  enabled: true
  command: "qwen"
  args: []
  env: {}
  supports_local: true
  local_model_config:
    auth_type: "openai"
    openai_base_url: "http://localhost:1234/v1"
    openai_api_key: "lm-studio"
    model: "qwen2.5-coder-7b-instruct"
```

### Execution Settings

```yaml
execution:
  create_git_checkpoint: true
  backup_before_changes: true
  max_file_size_mb: 10
  excluded_dirs: [".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"]
  excluded_files: [".env", "*.key", "*.pem", "*.secret"]
```

### Testing Settings

```yaml
testing:
  auto_detect: true
  run_after_changes: true
  commands:
    python: "pytest -v"
    javascript: "npm test"
    typescript: "npm test"
    rust: "cargo test"
    go: "go test ./..."
    dotnet: "dotnet test"
```

### Safety Settings

```yaml
safety:
  blocked_commands:
    - "rm -rf /"
    - "format"
    - "del /f /s /q"
    - "rd /s /q"
    - "reg delete"
    - "shutdown"
    - "taskkill /f"
    - "net user"
    - "net localgroup"
  blocked_paths:
    - "C:\\Windows"
    - "C:\\Program Files"
    - "C:\\Program Files (x86)"
    - "C:\\Users\\All Users"
    - "C:\\ProgramData"
  require_confirmation_for:
    - "delete"
    - "remove"
    - "format"
    - "uninstall"
```

### History Database

```yaml
history:
  enabled: true
  db_path: "C:\\Users\\NOUR SOFT\\Documents\\AI-Agent-Orchestrator\\orchestrator.db"
  max_entries: 1000
```

### Dashboard (Optional)

```yaml
dashboard:
  enabled: false
  port: 8765
  host: "127.0.0.1"
```

## Environment Variables

You can override config values with environment variables:

```cmd
set ORCHESTRATOR_LOG_LEVEL=DEBUG
set ORCHESTRATOR_MAX_RETRIES=5
set ORCHESTRATOR_WORKSPACE_DIR=D:\workspaces
```

## Per-Project Configuration

Create `.orchestrator.yaml` in your project root to override settings:

```yaml
# .orchestrator.yaml
agent_preferences:
  default_agent: "OpenCode"
execution:
  create_git_checkpoint: true
```

## Configuration Validation

Run `agent config --show` to view current configuration.

The orchestrator validates config on startup and will report any errors.