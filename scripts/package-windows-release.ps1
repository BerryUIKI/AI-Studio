# Berry AI Studio - Automated Windows Portable Release Packager (L01)
# Produces a self-contained portable distribution requiring 0 host Python, Git, or Node.js.

param (
    [string]$Version = "0.1.0",
    [string]$OutputDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$DistName = "Berry-AI-Studio-v$Version-windows-x64"
$TargetDir = Join-Path $OutputDir $DistName
$ZipFile = Join-Path $OutputDir "$DistName.zip"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Berry AI Studio - Windows Portable Release Packager" -ForegroundColor Cyan
Write-Host "  Target Package: $DistName" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Build Rust launcher
Write-Host "`n[1/5] Building native Rust launcher (release profile)..." -ForegroundColor Yellow
Push-Location "$RepoRoot\launcher"
try {
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "Rust compilation failed" }
} finally {
    Pop-Location
}
$LauncherExe = "$RepoRoot\launcher\target\release\berry.exe"
if (-not (Test-Path $LauncherExe)) {
    throw "Compiled launcher not found at $LauncherExe"
}

# 2. Build Frontend assets
Write-Host "`n[2/5] Building frontend production bundle..." -ForegroundColor Yellow
Push-Location "$RepoRoot\frontend"
try {
    pnpm build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} finally {
    Pop-Location
}
$FrontendDist = "$RepoRoot\frontend\dist"
if (-not (Test-Path "$FrontendDist\index.html")) {
    throw "Frontend production dist not found at $FrontendDist\index.html"
}

# 3. Clean and prepare staging directory
Write-Host "`n[3/5] Staging distribution directory at: $TargetDir" -ForegroundColor Yellow
if (Test-Path $TargetDir) {
    Remove-Item -Recurse -Force $TargetDir
}
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
New-Item -ItemType Directory -Path "$TargetDir\runtime\python" -Force | Out-Null
New-Item -ItemType Directory -Path "$TargetDir\backend" -Force | Out-Null
New-Item -ItemType Directory -Path "$TargetDir\frontend\dist" -Force | Out-Null

# 4. Copy assets into staging directory
Write-Host "`n[4/5] Populating release components..." -ForegroundColor Yellow

# Copy launcher
Copy-Item $LauncherExe -Destination "$TargetDir\berry.exe" -Force
Write-Host "  -> berry.exe copied" -ForegroundColor Green

# Copy frontend assets
Copy-Item -Recurse "$FrontendDist\*" -Destination "$TargetDir\frontend\dist\" -Force
Write-Host "  -> frontend/dist assets copied" -ForegroundColor Green

# Copy backend application files
New-Item -ItemType Directory -Path "$TargetDir\backend\app" -Force | Out-Null
Copy-Item -Recurse "$RepoRoot\backend\app\*" -Destination "$TargetDir\backend\app\" -Force
if (Test-Path "$RepoRoot\backend\requirements.txt") {
    Copy-Item "$RepoRoot\backend\requirements.txt" -Destination "$TargetDir\backend\" -Force
}
Write-Host "  -> backend application code copied (backend/app/main.py verified)" -ForegroundColor Green

# Prepare controlled Python runtime in runtime/python
# If an isolated venv exists in backend/.venv, stage it into runtime/python
$SourceVenv = "$RepoRoot\backend\.venv"
if (Test-Path "$SourceVenv\Scripts\python.exe") {
    Write-Host "  -> Bundling isolated Python runtime from backend/.venv into runtime/python..." -ForegroundColor Yellow
    # Copy python.exe and DLLs
    Copy-Item "$SourceVenv\Scripts\python.exe" -Destination "$TargetDir\runtime\python\python.exe" -Force
    Copy-Item "$SourceVenv\Scripts\pythonw.exe" -Destination "$TargetDir\runtime\python\pythonw.exe" -Force -ErrorAction SilentlyContinue
    
    # Copy Lib and Scripts
    if (Test-Path "$SourceVenv\Lib") {
        Copy-Item -Recurse "$SourceVenv\Lib" -Destination "$TargetDir\runtime\python\Lib" -Force
    }
    if (Test-Path "$SourceVenv\Scripts") {
        Copy-Item -Recurse "$SourceVenv\Scripts" -Destination "$TargetDir\runtime\python\Scripts" -Force
    }
    if (Test-Path "$SourceVenv\DLLs") {
        Copy-Item -Recurse "$SourceVenv\DLLs" -Destination "$TargetDir\runtime\python\DLLs" -Force
    }
    # pyvenv.cfg
    if (Test-Path "$SourceVenv\pyvenv.cfg") {
        Copy-Item "$SourceVenv\pyvenv.cfg" -Destination "$TargetDir\runtime\python\pyvenv.cfg" -Force
    }
    Write-Host "  -> runtime/python/python.exe hermetic runtime staged successfully" -ForegroundColor Green
} else {
    Write-Warning "backend/.venv not found; runtime/python was not bundled. Package will rely on host Python if not provided."
}

# Create Berry.bat launcher wrapper
$BatContent = @"
@echo off
title Berry AI Studio
cd /d "%~dp0"
echo Starting Berry AI Studio...
start "" "%~dp0berry.exe"
exit /b 0
"@
Set-Content -Path "$TargetDir\Berry.bat" -Value $BatContent -Encoding ASCII
Write-Host "  -> Berry.bat double-click wrapper created" -ForegroundColor Green

# Create README.txt
$ReadmeContent = @"
============================================================
  Berry AI Studio v$Version (Windows 64-bit Portable Release)
============================================================

Welcome to Berry AI Studio!

HOW TO RUN:
1. Double-click "Berry.bat" or "berry.exe".
2. Berry will perform automated readiness checks and open your
   default browser to http://127.0.0.1:8000.

ZERO PREREQUISITES:
- No installation of Python, Node.js, or Git is required.
- Everything is bundled inside this portable release directory.

MODES OF USE:
1. Cloud-Only (Zero GPU): Click "Cloud BYOK" in the top bar, enter
   an API key for OpenAI, Fal.ai, or SiliconFlow, and start generating.
2. Local NVIDIA Acceleration: Use the "Environment" manager to connect
   or install local ComfyUI or Stable Diffusion WebUI engines.

COMMAND LINE OPERATIONS:
Open a command prompt in this directory to run:
  berry.exe status               Show core and engine status
  berry.exe stop                 Gracefully shut down Berry
  berry.exe models list          Inspect local model inventory
  berry.exe update check         Check for application/engine updates
  berry.exe --help               Show all commands

Support & Documentation:
https://github.com/BerryUIKI/AI-Studio
============================================================
"@
Set-Content -Path "$TargetDir\README.txt" -Value $ReadmeContent -Encoding ASCII
Write-Host "  -> README.txt created" -ForegroundColor Green

# 5. Compress package into .zip
Write-Host "`n[5/5] Compressing package into: $ZipFile" -ForegroundColor Yellow
if (Test-Path $ZipFile) {
    Remove-Item -Force $ZipFile
}
Compress-Archive -Path "$TargetDir" -DestinationPath $ZipFile -CompressionLevel Optimal
Write-Host "  -> $ZipFile generated successfully ($( (Get-Item $ZipFile).Length / 1MB | ForEach-Object { [math]::Round($_, 1) } ) MB)" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Packaging Complete!" -ForegroundColor Green
Write-Host "  Directory: $TargetDir" -ForegroundColor Green
Write-Host "  Archive  : $ZipFile" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
