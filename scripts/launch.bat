@echo off
setlocal enabledelayedexpansion

title "Berry AI Studio Launcher & Environment Manager"

set ROOT_DIR=%~dp0..
set LAUNCHER_EXE_RELEASE=%ROOT_DIR%\launcher\target\release\berry.exe
set LAUNCHER_EXE_DEBUG=%ROOT_DIR%\launcher\target\debug\berry.exe
set CARGO_TOML=%ROOT_DIR%\launcher\Cargo.toml

:: 1. If release or debug Rust launcher exists, execute directly
if exist "%LAUNCHER_EXE_RELEASE%" (
    "%LAUNCHER_EXE_RELEASE%" %*
    exit /b %ERRORLEVEL%
)

if exist "%LAUNCHER_EXE_DEBUG%" (
    "%LAUNCHER_EXE_DEBUG%" %*
    exit /b %ERRORLEVEL%
)

:: 2. If Rust toolchain is available, build and run launcher
where cargo >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [*] Building Berry AI Studio Rust launcher...
    cargo run --release --manifest-path "%CARGO_TOML%" -- %*
    exit /b %ERRORLEVEL%
)

:: 3. Standalone Python bootstrap fallback if Rust toolchain not installed on machine
echo ========================================================
echo               Berry AI Studio (Windows)
echo ========================================================
echo.

set BACKEND_DIR=%ROOT_DIR%\backend
set VENV_DIR=%BACKEND_DIR%\.venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.10+ was not found on your system PATH.
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

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

echo [2/3] Starting Berry AI Studio on http://127.0.0.1:8000 ...
cd /d "%BACKEND_DIR%"
start "" "%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo [3/3] Waiting for backend readiness probe...
:wait_loop
timeout /t 1 /nobreak >nul
curl -s http://127.0.0.1:8000/health | findstr "ai-workflow-backend" >nul
if %ERRORLEVEL% neq 0 (
    goto wait_loop
)

echo [*] Opening creative workspace in default browser...
start "" "http://127.0.0.1:8000"
