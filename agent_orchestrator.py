#!/usr/bin/env python3
"""
AI Coding Agent Orchestrator
Main entry point for the orchestrator system.
"""

import sys
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.cli.main import main

if __name__ == "__main__":
    sys.exit(main())