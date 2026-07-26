@echo off
REM Double-click this file to open this project in Cursor.
setlocal

set "CURSOR_EXE=%LOCALAPPDATA%\Programs\cursor\Cursor.exe"
if not exist "%CURSOR_EXE%" set "CURSOR_EXE=%LOCALAPPDATA%\Programs\Cursor\Cursor.exe"

if not exist "%CURSOR_EXE%" (
    echo Cursor was not found. Install Cursor or edit this script with the correct path.
    pause
    exit /b 1
)

REM Open the workspace file in this folder (same folder as this script).
start "" "%CURSOR_EXE%" "%~dp0rvBackupHelper.code-workspace"
