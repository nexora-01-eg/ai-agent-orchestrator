# Architecture

## Overview

The system is now an **Autonomous AI Coding Supervisor** layered over the
original orchestrator (which is kept intact and reused). New supervisor
modules live in `orchestrator/core/` and `orchestrator/agents/`:

```
CLI -> Supervisor -> [ProjectAnalyzer | TaskPlanner | AgentMatrix(live)
      | ModelDiscovery | SmartRouter | SecurityGate] -> Adapters
      -> TestGate + ChangeReview -> Observability(logs/*.log + report.json)
      + SQLite history. Optional: Dashboard(:8787), Scheduler(stored-only).
```

Details: see `SUPERVISOR.md`. The original orchestrator architecture below
is preserved; the supervisor calls into it (factory, adapters, database)
instead of replacing it.

## Original Orchestrator Architecture

The AI Coding Agent Orchestrator follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                             │
│  (orchestrator/cli/main.py, commands.py)                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                     Execution Engine                         │
│  (orchestrator/core/engine.py)                              │
│  - Task orchestration                                       │
│  - Retry logic                                              │
│  - Test execution                                           │
│  - Git checkpointing                                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ Task Analyzer │ │ Agent Selector│ │  History DB   │
│ (analyzer.py) │ │ (analyzer.py) │ │ (database.py) │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    Adapter Factory                           │
│              (adapters/factory.py)                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  OpenCode     │ │    Aider      │ │   Gemini      │
│  Adapter      │ │   Adapter     │ │   Adapter     │
└───────────────┘ └───────────────┘ └───────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│    Qwen       │ │  LM Studio    │ │  (Future)     │
│   Adapter     │ │   Adapter     │ │   Agents      │
└───────────────┘ └───────────────┘ └───────────────┘
```

## Core Components

### 1. Configuration Manager (`core/config.py`)

- Loads and validates YAML configuration
- Provides typed config objects
- Manages agent configurations
- Reads agent status from `agents.json`

### 2. History Database (`core/database.py`)

- SQLite database for task history
- Tracks: task_id, project, agent, model, attempts, duration, results
- Indexes for fast queries by date, agent, project
- Automatic cleanup of old entries

### 3. Task Analyzer (`core/analyzer.py`)

- Analyzes project structure (language, framework, type)
- Estimates task complexity, size, risk
- Identifies likely affected files and required commands

### 4. Agent Selector (`core/analyzer.py`)

- Scores available agents based on task analysis
- Prefers local models when configured
- Considers agent capabilities (git, local models, test running)

### 5. Execution Engine (`core/engine.py`)

- Orchestrates task execution
- Manages retry logic with error analysis
- Creates git checkpoints
- Runs tests after changes
- Records execution logs

### 6. Adapter System (`adapters/`)

- **BaseAdapter**: Abstract base class with common functionality
- **OpenCodeAdapter**: PowerShell script execution
- **AiderAdapter**: Command-line with model config
- **GeminiAdapter**: OAuth/API key authentication
- **QwenAdapter**: Multi-auth support
- **LMStudioAdapter**: Local model server API

### 7. Adapter Factory (`adapters/factory.py`)

- Creates adapter instances
- Filters available/working agents
- Extensible for new agents

## Data Flow

```
User Task
    │
    ▼
Task Analyzer → Project Analysis
    │
    ▼
Agent Selector → Best Agent
    │
    ▼
Execution Engine
    │
    ├──▶ Git Checkpoint
    │
    ├──▶ Adapter.Execute() → Agent CLI
    │       │
    │       ├──▶ Retry on failure (max 3)
    │       │
    │       └──▶ Parse output
    │
    ├──▶ Test Detection & Execution
    │
    └──▶ History Database
```

## Extension Points

1. **New Agents**: Add adapter class + register in factory
2. **New Test Commands**: Add to config.yaml testing section
3. **New Analysis Rules**: Extend TaskAnalyzer
4. **New Selection Criteria**: Extend AgentSelector
5. **New Retry Strategies**: Extend _analyze_failure_and_prepare_retry