@echo off
REM Double-click this file to launch the app (no terminal needed).
setlocal

REM pythonw.exe runs the GUI without keeping a console window open.
set "VENV_PYW=%~dp0.venv\Scripts\pythonw.exe"

if not exist "%VENV_PYW%" (
    echo Virtual environment not found. Run the one-time setup first ^(see README.md^):
    echo.
    echo     python -m venv .venv
    echo     .venv\Scripts\Activate.ps1
    echo     pip install -e ".[dev]"
    echo.
    pause
    exit /b 1
)

start "" "%VENV_PYW%" -m rvBackupHelper.main
