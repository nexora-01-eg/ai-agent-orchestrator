# Troubleshooting Guide

## Common Issues

### 1. Python Not Found / Windows Store Alias

**Symptoms**:
```
python : Python was not found; run without arguments to install from the Microsoft Store...
```

**Cause**: Windows Store Python alias intercepts `python` command.

**Solution**:
1. Run `Fix-Python-Path.ps1` as Administrator
2. Or manually disable in Settings:
   - Settings > Apps > Advanced app settings > App execution aliases
   - Turn OFF "Python 3.11" and "Python 3.12"
3. Use full path: `C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe`

### 2. OpenCode Not Found / PowerShell Script

**Symptoms**:
```
FileNotFoundError: [WinError 2] The system cannot find the file specified
```

**Cause**: OpenCode installs as PowerShell script (`.ps1`), not executable.

**Solution**: Ensure config.yaml has correct path:
```yaml
OpenCode:
  path: "C:\\Users\\NOUR SOFT\\AppData\\Roaming\\npm\\opencode.ps1"
```

The adapter automatically detects and runs via PowerShell.

### 3. Aider: "No connection could be made" / Ollama Error

**Symptoms**:
```
OllamaError: Error getting model info... No connection could be made because the target machine actively refused it
```

**Cause**: LM Studio or Ollama server not running.

**Solution**:
1. Install LM Studio from https://lmstudio.ai
2. Download a model (e.g., qwen2.5-coder-7b-instruct)
3. Start server on port 1234
4. Verify: `curl http://localhost:1234/v1/models`

### 4. Gemini CLI: "Please set an Auth method"

**Symptoms**:
```
Please set an Auth method in your C:\Users\...\settings.json or specify GEMINI_API_KEY...
```

**Cause**: No authentication configured.

**Solution**:
```bash
gemini auth
# Follow OAuth flow with Google account
```
Or set environment variable:
```cmd
set GEMINI_API_KEY=your-api-key
```

### 5. Qwen Code: "No auth type is selected"

**Symptoms**:
```
No auth type is selected. Please configure an auth type...
```

**Solution**:
```bash
qwen auth
# Or use command line:
qwen --auth-type openai --openai-base-url http://localhost:1234/v1 --openai-api-key lm-studio -p "task"
```

### 6. Agent Not Working After Install

**Symptoms**: Agent shows "NOT TESTED" or "BLOCKED" in `agent list`

**Solution**:
1. Run `agent doctor` to see specific issues
2. Check agent-specific requirements above
3. Verify PATH includes agent installation directories

### 7. "No working agents available"

**Symptoms**:
```
Error: No working agents available. Check agents.json and local model server.
```

**Solution**:
1. Run `agent doctor` to diagnose
2. Ensure at least one agent is working (OpenCode usually works out of box)
3. Start LM Studio for local model support
4. Configure authentication for cloud agents

### 8. Test Command Not Detected

**Symptoms**: "No test command detected" after task

**Solution**: Add test script to project:
- Python: `pytest.ini` or `pyproject.toml` with `[tool.pytest]`
- Node.js: `"test": "jest"` in package.json scripts
- Rust: `cargo test` works automatically

Or configure in config.yaml:
```yaml
testing:
  commands:
    python: "python -m pytest"
```

### 9. Permission Errors

**Symptoms**: "Access denied" or "Permission denied"

**Solution**:
1. Run terminal as Administrator (for system-wide changes)
2. Check file/folder permissions
3. Ensure project not in protected path (C:\Windows, etc.)

### 10. Task Timeout

**Symptoms**: Task fails with "Execution timeout"

**Solution**: Increase timeout in config.yaml:
```yaml
general:
  default_timeout: 600  # 10 minutes
```
Or per-task:
```bash
agent run --project ... --task ... --timeout 600
```

## Debugging

### Enable Debug Logging

```cmd
set ORCHESTRATOR_LOG_LEVEL=DEBUG
agent run --project ... --task ...
```

### View Execution Logs

```bash
agent history --limit 5
```

### Check Agent Health

```bash
agent doctor
```

### Verify Agent Installation

```bash
opencode --version
aider --version
gemini --version
qwen --version
```

### Test Local Model Server

```bash
curl http://localhost:1234/v1/models
curl http://localhost:11434/v1/models
```

## Getting Help

1. Run `agent doctor` for system diagnostics
2. Check `agent history` for recent task logs
3. Review this troubleshooting guide
4. Check GitHub issues for known problems
5. Enable debug logging for detailed output

## Reporting Bugs

When reporting issues, include:

1. Output of `agent doctor`
2. Output of `agent history --limit 3`
3. Task description that failed
4. Error messages
5. OS version (`systeminfo | findstr OS`)
6. Python/Node versions