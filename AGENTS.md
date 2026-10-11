# Supported Agents

## Overview

The orchestrator supports multiple AI coding agents through a unified adapter interface. Each agent has different strengths and requirements.

## Agent Comparison

| Feature | OpenCode | Aider | Gemini CLI | Qwen Code |
|---------|----------|-------|------------|-----------|
| **License** | MIT | Apache 2.0 | Apache 2.0 | Apache 2.0 |
| **Local Models** | ✅ | ✅ | ❌ | ✅ |
| **Free Tier** | ✅ | ✅ | ✅ (60/min) | ✅ (self-hosted) |
| **Auth Required** | ❌ | ❌ | ✅ | ✅ |
| **Git Native** | ✅ | ✅ (auto-commit) | ✅ | ✅ |
| **MCP Support** | ✅ | ❌ | ✅ | ✅ |
| **Agent Teams** | ✅ | ❌ | ❌ | ✅ |
| **Windows** | ✅ | ✅ | ✅ | ✅ |

## OpenCode

**Status**: ✅ WORKING (Tested)

**Path**: `C:\Users\NOUR SOFT\AppData\Roaming\npm\opencode.ps1`

**Version**: 1.18.31

**Capabilities**:
- File read/write/edit
- Terminal/shell commands
- Local models (Ollama, LM Studio, OpenAI-compatible)
- MCP servers
- Agent teams
- Auto-approval modes

**Configuration**:
```yaml
OpenCode:
  enabled: true
  command: "opencode"
  path: "C:\\Users\\NOUR SOFT\\AppData\\Roaming\\npm\\opencode.ps1"
  args: []
  supports_local: true
  local_model_config:
    provider: "openai_compatible"
    base_url: "http://localhost:1234/v1"
    api_key: "lm-studio"
    model: "qwen2.5-coder-7b-instruct"
```

**Best For**: General purpose coding, multi-file tasks, local models

**Notes**: Runs as PowerShell script. Requires full path in config.

## Aider

**Status**: ⚠️ BLOCKED (Needs LM Studio/Ollama running)

**Path**: `C:\Users\NOUR SOFT\.local\bin\aider.exe`

**Version**: 0.86.2

**Capabilities**:
- File read/write/edit
- Terminal/shell commands
- Git-native (auto-commits)
- Local models (Ollama, LM Studio, OpenAI-compatible)
- Architect mode for planning
- Repo map for context

**Configuration**:
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

**Best For**: Git-focused workflows, incremental changes, test-driven development

**Requirements**: LM Studio or Ollama must be running

**Notes**: Uses `aider-install` for isolated environment. Terminal issues on Windows without proper console.

## Gemini CLI

**Status**: ⚠️ BLOCKED (Needs Google authentication)

**Path**: `C:\Users\NOUR SOFT\AppData\Roaming\npm\gemini.ps1`

**Version**: 0.60.0

**Capabilities**:
- File read/write/edit
- Terminal/shell commands
- Google Search grounding
- MCP servers
- Extensions/skills
- Web fetching

**Configuration**:
```yaml
Gemini:
  enabled: true
  command: "gemini"
  args: []
  supports_local: false
  requires_auth: true
```

**Best For**: Research tasks, web searches, Google ecosystem

**Authentication Methods**:
1. `gemini auth` - Google OAuth (free tier: 60 req/min, 1000/day)
2. `GEMINI_API_KEY` - API key
3. `GOOGLE_GENAI_USE_VERTEXAI` - Vertex AI

**Notes**: No local model support. Requires internet.

## Qwen Code

**Status**: ⚠️ BLOCKED (Needs authentication config)

**Path**: `C:\Users\NOUR SOFT\AppData\Roaming\npm\qwen.ps1`

**Version**: 0.24.0

**Capabilities**:
- File read/write/edit
- Terminal/shell commands
- Local models (Ollama, vLLM, LM Studio, OpenAI-compatible)
- Agent teams / sub-agents
- MCP servers
- Skills (review, batch, loop, bugfix)
- Daemon mode
- IM bots (Telegram, Discord, etc.)

**Configuration**:
```yaml
Qwen:
  enabled: true
  command: "qwen"
  args: []
  supports_local: true
  local_model_config:
    auth_type: "openai"
    openai_base_url: "http://localhost:1234/v1"
    openai_api_key: "lm-studio"
    model: "qwen2.5-coder-7b-instruct"
```

**Best For**: Complex orchestration, agent teams, Qwen ecosystem

**Authentication Methods**:
1. `--auth-type openai` + `--openai-base-url` + `--openai-api-key` (local)
2. `--auth-type qwen-oauth` (Qwen OAuth)
3. `--auth-type anthropic` (Anthropic)
4. `--auth-type gemini` (Gemini)
5. `--auth-type vertex-ai` (Vertex AI)

**Notes**: Fork of Gemini CLI. Very flexible provider support.

## Local Model Servers

### LM Studio (Recommended for Windows)

- **Download**: https://lmstudio.ai
- **Port**: 1234 (default)
- **API**: OpenAI-compatible `/v1`
- **Models**: GGUF format
- **Best Models for Coding**:
  - qwen2.5-coder-7b-instruct (Q4_K_M) - ~4.7 GB
  - deepseek-coder-6.7b-instruct (Q4_K_M) - ~3.8 GB
  - phi-3-mini-4k-instruct (Q4_K_M) - ~2.3 GB

### Ollama

- **Download**: https://ollama.com
- **Port**: 11434 (default)
- **API**: OpenAI-compatible `/v1`
- **Models**: GGUF format
- **Best Models for Coding**:
  - qwen2.5-coder:7b
  - deepseek-coder:6.7b
  - codellama:7b

## Agent Selection Logic

The orchestrator automatically selects the best agent based on:

1. **Local Model Preference** → OpenCode, Aider, Qwen (if LM Studio running)
2. **Git-Focused Tasks** → Aider
3. **Large Multi-File Tasks** → OpenCode
4. **Complex Orchestration** → Qwen Code
5. **Research/Web Tasks** → Gemini CLI
6. **Fallback** → First available working agent

## Adding New Agents

1. Create adapter in `orchestrator/adapters/`
2. Inherit from `BaseAgentAdapter`
3. Implement required methods:
   - `agent_name` property
   - `get_capabilities()`
   - `check_available()`
   - `prepare_command()`
   - `parse_output()`
4. Register in `adapters/factory.py`
5. Add config to `config.yaml`