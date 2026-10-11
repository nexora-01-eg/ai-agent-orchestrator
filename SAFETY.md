# Safety Guidelines

## Overview

The AI Coding Agent Orchestrator implements multiple safety layers to protect your system and data.

## Safety Features

### 1. Git Checkpoints

Before any task execution, the orchestrator creates a git checkpoint:

```bash
git add -A
git commit -m "Orchestrator checkpoint for task <task_id>"
```

This allows easy rollback if something goes wrong.

### 2. Blocked Commands

The following commands are blocked and will never be executed:

- `rm -rf /` - Recursive root deletion
- `format` - Disk formatting
- `del /f /s /q` - Force delete all files
- `rd /s /q` - Remove directory tree
- `reg delete` - Registry deletion
- `shutdown` - System shutdown
- `taskkill /f` - Force kill processes
- `net user` - User management
- `net localgroup` - Group management

Add to `config.yaml`:
```yaml
safety:
  blocked_commands:
    - "your-custom-blocked-command"
```

### 3. Blocked Paths

The following paths are protected and cannot be modified:

- `C:\Windows`
- `C:\Program Files`
- `C:\Program Files (x86)`
- `C:\Users\All Users`
- `C:\ProgramData`

Add to `config.yaml`:
```yaml
safety:
  blocked_paths:
    - "C:\\Your\\Protected\\Path"
```

### 4. Confirmation for Destructive Operations

Operations matching these patterns require explicit confirmation:

- `delete`
- `remove`
- `format`
- `uninstall`

Configure in `config.yaml`:
```yaml
safety:
  require_confirmation_for:
    - "your-custom-pattern"
```

### 5. No Credential Handling

The orchestrator:
- Never stores API keys in code
- Never sends credentials to external services
- Uses environment variables for secrets
- Reads API keys from config.yaml (which should be gitignored)

### 6. No Automatic Git Push

The orchestrator:
- Creates local commits only
- Never runs `git push` automatically
- User must manually push changes

### 7. Workspace Isolation

Each task runs in the specified project directory. The orchestrator:
- Validates project path exists
- Never modifies files outside project
- Uses relative paths internally

### 7. File Size Limits

Maximum file size for operations: 10 MB (configurable)

```yaml
execution:
  max_file_size_mb: 10
```

## Best Practices

### Before Running Tasks

1. **Commit your work** - Ensure clean git state
2. **Review the task** - Understand what will be changed
3. **Check agent status** - Run `agent doctor` first
4. **Backup important data** - Especially for first runs

### During Execution

1. **Monitor logs** - Watch for unexpected behavior
2. **Use Ctrl+C** - Can interrupt at any time
3. **Check git status** - `git status` shows pending changes

### After Execution

1. **Review changes** - `git diff` shows modifications
2. **Run tests** - Verify functionality
3. **Commit manually** - Only push when satisfied

## Emergency Procedures

### If Something Goes Wrong

1. **Stop the task**: Press Ctrl+C
2. **Check git status**: `git status`
3. **Rollback if needed**: `git reset --hard HEAD~1`
4. **Check orchestrator logs**: In task history

### If System Files Modified

1. **Do not panic** - Windows protects system files
2. **Check blocked paths** - Should have been prevented
3. **Run system file checker**: `sfc /scannow`

## Security Considerations

### API Keys

- Store in config.yaml (add to .gitignore)
- Use environment variables for CI/CD
- Rotate keys regularly

### Local Models

- LM Studio/Ollama run locally
- No data leaves your machine
- Verify model sources (official repos only)

### Network Access

- Agents may access internet for:
  - Package installation (npm, pip, cargo)
  - API calls (if using cloud models)
  - Web searches (Gemini CLI)
- Block in firewall if needed

## Reporting Issues

If you find a safety issue:

1. Stop using the orchestrator
2. Document the issue
3. Report via GitHub issues
4. Include logs and steps to reproduce