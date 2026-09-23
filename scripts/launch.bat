@echo off
setlocal enabledelayedexpansion

title Berry AI Studio Launcher
echo ========================================================
echo               Berry AI Studio (Windows)
echo ========================================================
echo.

set ROOT_DIR=%~dp0..
set BACKEND_DIR=%ROOT_DIR%\backend
set FRONTEND_DIR=%ROOT_DIR%\frontend
set VENV_DIR=%BACKEND_DIR%\.venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe

:: 1. Check Python installation on host
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.10+ was not found on your system PATH.
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)

:: 2. Initialize isolated virtual environment if missing
if not exist "%PYTHON_EXE%" (
    echo [1/3] Initializing isolated virtual environment...
    python -m venv "%VENV_DIR%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [2/3] Installing dependencies into isolated environment...
    "%PYTHON_EXE%" -m pip install --upgrade pip
    "%PYTHON_EXE%" -m pip install -r "%BACKEND_DIR%\requirements.txt"
) else (
    echo [1/3] Sandboxed virtual environment verified.
)

:: 3. Launch application server on loopback
echo [3/3] Starting Berry AI Studio on http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"

cd /d "%BACKEND_DIR%"
"%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
