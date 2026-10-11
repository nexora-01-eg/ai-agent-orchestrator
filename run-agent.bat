@echo off
REM AI Coding Agent Orchestrator - Windows Launcher
REM This script runs the orchestrator CLI

set PROJECT_ROOT=C:\Users\NOUR SOFT\Documents\AI-Agent-Orchestrator
set PYTHON=C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe

if not exist "%PYTHON%" (
    echo Error: Python not found at %PYTHON%
    echo Please run Fix-Python-Path.ps1 as Administrator or install Python
    pause
    exit /b 1
)

if not exist "%PROJECT_ROOT%\agent_orchestrator.py" (
    echo Error: Orchestrator not found at %PROJECT_ROOT%
    pause
    exit /b 1
)

cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py %*