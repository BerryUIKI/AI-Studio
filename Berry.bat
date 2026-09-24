@echo off
setlocal
cd /d "%~dp0"
title Berry AI Studio

echo ========================================================
echo              Berry AI Studio Desktop App
echo ========================================================
echo.

if exist "Berry AI Studio.exe" (
    echo Launching Berry AI Studio native desktop application...
    start "" "Berry AI Studio.exe"
    exit /b 0
)

if exist "frontend\src-tauri\target\release\Berry AI Studio.exe" (
    echo Launching Berry AI Studio native desktop application...
    start "" "frontend\src-tauri\target\release\Berry AI Studio.exe"
    exit /b 0
)

if exist "dist\Berry-AI-Studio-v0.1.0-windows-x64\Berry AI Studio.exe" (
    echo Launching Berry AI Studio native desktop application...
    start "" "dist\Berry-AI-Studio-v0.1.0-windows-x64\Berry AI Studio.exe"
    exit /b 0
)

if exist "frontend\src-tauri\target\release\berry-app.exe" (
    echo Launching Berry AI Studio native desktop application...
    start "" "frontend\src-tauri\target\release\berry-app.exe"
    exit /b 0
)

echo Starting Berry AI Studio in Desktop mode...
pnpm --prefix frontend tauri dev
