@echo off
REM AI Coding Agent Orchestrator - Doctor (Diagnostics)

set PROJECT_ROOT=C:\Users\NOUR SOFT\Documents\AI-Agent-Orchestrator
set PYTHON=C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe

if not exist "%PYTHON%" (
    echo Error: Python not found at %PYTHON%
    pause
    exit /b 1
)

cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py doctor
pause