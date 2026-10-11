@echo off
REM AI Coding Supervisor - One-Command Experience

set PROJECT_ROOT=C:\Users\NOUR SOFT\Documents\AI-Agent-Orchestrator
set PYTHON=C:\Users\NOUR SOFT\AppData\Local\Programs\Python\Python311\python.exe

if not exist "%PYTHON%" (
    echo Error: Python not found at %PYTHON%
    echo Please run Fix-Python-Path.ps1 as Administrator
    pause
    exit /b 1
)

:MENU
cls
echo ==========================================
echo   AI CODING SUPERVISOR
echo   "Tell it the problem, it handles the rest"
echo ==========================================
echo.
echo 1. Analyze Project
echo 2. Run Task
echo 3. Autonomous Task
echo 4. Multi-Agent Task
echo 5. Compare Agents
echo 6. Check System
echo 7. View History
echo 8. Dashboard
echo 9. Settings
echo 10. Exit
echo.
set /p CHOICE=Select option [1-10]:

if "%CHOICE%"=="1" goto ANALYZE
if "%CHOICE%"=="2" goto RUNTASK
if "%CHOICE%"=="3" goto AUTONOMOUS
if "%CHOICE%"=="4" goto MULTI
if "%CHOICE%"=="5" goto COMPARE
if "%CHOICE%"=="6" goto DOCTOR
if "%CHOICE%"=="7" goto HISTORY
if "%CHOICE%"=="8" goto DASHBOARD
if "%CHOICE%"=="9" goto SETTINGS
if "%CHOICE%"=="10" goto EXIT

echo Invalid choice. Press any key to continue...
pause
goto MENU

:ASKPROJECT
set /p PROJECT=Project Path:
if "%PROJECT%"=="" (
    echo Project path required!
    pause
    goto MENU
)
goto :EOF

:ANALYZE
cls
echo === Analyze Project (read-only, never edits) ===
echo.
call :ASKPROJECT
set /p TASK=Task description (optional, Enter to skip):
cd /d "%PROJECT_ROOT%"
if "%TASK%"=="" (
    "%PYTHON%" agent_orchestrator.py analyze --project "%PROJECT%"
) else (
    "%PYTHON%" agent_orchestrator.py analyze --project "%PROJECT%" --task "%TASK%"
)
pause
goto MENU

:RUNTASK
cls
echo === Run Task (Supervisor: plan, route, execute, validate, test) ===
echo Just describe the problem, e.g. "fix the login bug in this project".
echo.
call :ASKPROJECT
set /p TASK=Task description:
if "%TASK%"=="" (
    echo Task description required!
    pause
    goto MENU
)
cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py run --project "%PROJECT%" --task "%TASK%" --mode AUTO
pause
goto MENU

:AUTONOMOUS
cls
echo === Autonomous Task (PLAN - EXECUTE - TEST - REPAIR - REPORT) ===
echo Bounded repair attempts. High-risk steps ask for approval.
echo.
call :ASKPROJECT
set /p TASK=Task description:
if "%TASK%"=="" (
    echo Task description required!
    pause
    goto MENU
)
cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py run --project "%PROJECT%" --task "%TASK%" --autonomous
pause
goto MENU

:MULTI
cls
echo === Multi-Agent Task (isolated workspaces, original untouched) ===
echo.
call :ASKPROJECT
set /p TASK=Task description:
if "%TASK%"=="" (
    echo Task description required!
    pause
    goto MENU
)
cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py run --project "%PROJECT%" --task "%TASK%" --multi
pause
goto MENU

:COMPARE
cls
echo === Compare Agents ===
echo.
call :ASKPROJECT
set /p TASK=Task description:
if "%TASK%"=="" (
    echo Task description required!
    pause
    goto MENU
)
cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py compare --project "%PROJECT%" --task "%TASK%"
pause
goto MENU

:DOCTOR
cls
echo === Check System (live health) ===
echo.
cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py doctor
pause
goto MENU

:HISTORY
cls
echo === View History ===
echo.
cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py history --limit 20
pause
goto MENU

:DASHBOARD
cls
echo === Dashboard (local, optional) ===
echo Opens http://127.0.0.1:8787 - press Ctrl+C to stop.
echo.
cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py dashboard --port 8787
pause
goto MENU

:SETTINGS
cls
echo === Settings ===
echo.
cd /d "%PROJECT_ROOT%"
"%PYTHON%" agent_orchestrator.py config --show
pause
goto MENU

:EXIT
echo Goodbye!
timeout /t 1 >nul
exit
