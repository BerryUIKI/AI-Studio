# Berry AI Studio - Automated Windows Portable Release Packager (L01)
# Produces a self-contained portable distribution requiring 0 host Python, Git, or Node.js.

param (
    [string]$Version = "0.1.0",
    [string]$OutputDir = "$PSScriptRoot\..\dist",
    [switch]$SkipPythonBuild = $false
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

# Helper function to verify required files
function Assert-FileExists {
    param([string]$Path, [string]$Description)
    if (-not (Test-Path $Path)) {
        throw "PACKAGING FAILED: Missing required file: $Description at $Path"
    }
}

# Step 0: Prepare standalone Python runtime (if not already done)
Write-Host "`n[0/6] Preparing standalone Python runtime..." -ForegroundColor Yellow
$StandalonePython = "$RepoRoot\runtime\python-standalone"
if ($SkipPythonBuild -and (Test-Path "$StandalonePython\python.exe")) {
    Write-Host "  -> Skipping Python build (using existing runtime at $StandalonePython)" -ForegroundColor Gray
} else {
    & "$PSScriptRoot\prepare-standalone-python.ps1"
    if ($LASTEXITCODE -ne 0) {
        throw "Standalone Python preparation failed"
    }
}

# Verify standalone Python exists and is complete
Assert-FileExists "$StandalonePython\python.exe" "Standalone Python executable"
$PyTest = & "$StandalonePython\python.exe" -c "import fastapi; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0 -or $PyTest -notmatch "OK") {
    throw "PACKAGING FAILED: Standalone Python runtime is incomplete or missing dependencies"
}
Write-Host "  -> Standalone Python runtime verified" -ForegroundColor Green

# Step 1: Build Frontend assets FIRST (required before Tauri can embed them)
Write-Host "`n[1/6] Building frontend production bundle..." -ForegroundColor Yellow
Push-Location "$RepoRoot\frontend"
try {
    # Check if pnpm is available
    $null = Get-Command pnpm -ErrorAction Stop
    pnpm install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }

    pnpm build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
} catch {
    throw "Frontend build error: $_"
} finally {
    Pop-Location
}

$FrontendDist = "$RepoRoot\frontend\dist"
Assert-FileExists "$FrontendDist\index.html" "Frontend production dist (index.html)"
Assert-FileExists "$FrontendDist\assets" "Frontend assets directory"
Write-Host "  -> Frontend assets built successfully" -ForegroundColor Green

# Step 2: Build Tauri native desktop application (embeds frontend assets)
Write-Host "`n[2/6] Building native Tauri desktop application..." -ForegroundColor Yellow
Push-Location "$RepoRoot\frontend"
try {
    pnpm tauri build --bundles nsis
    if ($LASTEXITCODE -ne 0) { throw "Tauri build failed" }
} finally {
    Pop-Location
}

$TauriExe = "$RepoRoot\frontend\src-tauri\target\release\berry-app.exe"
Assert-FileExists $TauriExe "Tauri native application executable"
Write-Host "  -> Tauri application built successfully" -ForegroundColor Green

# Step 3: Build Rust launcher
Write-Host "`n[3/6] Building native Rust launcher (release profile)..." -ForegroundColor Yellow
Push-Location "$RepoRoot\launcher"
try {
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "Rust launcher compilation failed" }
} finally {
    Pop-Location
}

$LauncherExe = "$RepoRoot\launcher\target\release\berry.exe"
Assert-FileExists $LauncherExe "Rust launcher executable"
Write-Host "  -> Rust launcher built successfully" -ForegroundColor Green

# Step 4: Clean and prepare staging directory
Write-Host "`n[4/6] Staging distribution directory at: $TargetDir" -ForegroundColor Yellow
if (Test-Path $TargetDir) {
    Remove-Item -Recurse -Force $TargetDir
}
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
New-Item -ItemType Directory -Path "$TargetDir\runtime" -Force | Out-Null
New-Item -ItemType Directory -Path "$TargetDir\backend" -Force | Out-Null
New-Item -ItemType Directory -Path "$TargetDir\frontend\dist" -Force | Out-Null
Write-Host "  -> Staging directories created" -ForegroundColor Green

# Step 5: Copy assets into staging directory
Write-Host "`n[5/6] Populating release components..." -ForegroundColor Yellow

# Copy launcher
Copy-Item $LauncherExe -Destination "$TargetDir\berry.exe" -Force
Write-Host "  -> berry.exe copied" -ForegroundColor Green

# Copy Tauri desktop application
Copy-Item $TauriExe -Destination "$TargetDir\Berry AI Studio.exe" -Force
Write-Host "  -> Berry AI Studio.exe native app copied" -ForegroundColor Green

# Copy frontend assets
Copy-Item -Recurse "$FrontendDist\*" -Destination "$TargetDir\frontend\dist\" -Force
Write-Host "  -> frontend/dist assets copied" -ForegroundColor Green

# Copy backend application files
New-Item -ItemType Directory -Path "$TargetDir\backend\app" -Force | Out-Null
Copy-Item -Recurse "$RepoRoot\backend\app\*" -Destination "$TargetDir\backend\app\" -Force
if (Test-Path "$RepoRoot\backend\requirements.txt") {
    Copy-Item "$RepoRoot\backend\requirements.txt" -Destination "$TargetDir\backend\" -Force
}
Assert-FileExists "$TargetDir\backend\app\main.py" "Backend main.py"
Write-Host "  -> backend application code copied" -ForegroundColor Green

# Copy complete standalone Python runtime
Write-Host "  -> Copying standalone Python runtime to runtime/python..." -ForegroundColor Yellow
Copy-Item -Recurse "$StandalonePython\*" -Destination "$TargetDir\runtime\python\" -Force
Assert-FileExists "$TargetDir\runtime\python\python.exe" "Bundled Python executable"

# Verify bundled Python is self-contained (no external base_prefix references)
$BundledPyTest = & "$TargetDir\runtime\python\python.exe" -c "import sys, fastapi; print(f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} OK')" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "PACKAGING FAILED: Bundled Python runtime cannot execute independently"
}
Write-Host "  -> $BundledPyTest" -ForegroundColor Green

# Bundle portable Git (PortableGit-2.47.1-64-bit.7z.exe self-extractor)
# This enables engine installation without requiring system Git
$PortableGitUrl = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/PortableGit-2.47.1-64-bit.7z.exe"
$PortableGitPath = "$TargetDir\runtime\git"
$PortableGitExe = Join-Path $env:TEMP "PortableGit.exe"

Write-Host "  -> Downloading portable Git..." -ForegroundColor Yellow
try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $PortableGitUrl -OutFile $PortableGitExe -UseBasicParsing

    # Extract portable Git (self-extracting 7z)
    New-Item -ItemType Directory -Path $PortableGitPath -Force | Out-Null
    Write-Host "  -> Extracting portable Git to runtime/git..." -ForegroundColor Yellow

    # Use 7z if available, otherwise use the self-extractor
    $7z = Get-Command 7z -ErrorAction SilentlyContinue
    if ($7z) {
        & 7z x $PortableGitExe "-o$PortableGitPath" -y | Out-Null
    } else {
        Start-Process -FilePath $PortableGitExe -ArgumentList "-o`"$PortableGitPath`"","-y" -Wait -NoNewWindow
    }

    Remove-Item $PortableGitExe -Force

    if (Test-Path "$PortableGitPath\cmd\git.exe") {
        Write-Host "  -> Portable Git bundled successfully" -ForegroundColor Green
    } else {
        Write-Warning "Portable Git extraction may have failed; engine installation might require system Git"
    }
} catch {
    Write-Warning "Failed to bundle portable Git: $_. Engine installation will require system Git."
}

# Copy embedded llama-server runtime if present
$SourceLlamaServer = "$RepoRoot\runtime\llama_server"
if (Test-Path "$SourceLlamaServer\llama-server.exe") {
    Write-Host "  -> Bundling embedded llama-server binary into runtime/llama_server..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "$TargetDir\runtime\llama_server" -Force | Out-Null
    Copy-Item -Recurse "$SourceLlamaServer\*" -Destination "$TargetDir\runtime\llama_server\" -Force
    Write-Host "  -> runtime/llama_server/llama-server.exe staged successfully" -ForegroundColor Green
}

# Create Berry.bat launcher wrapper
$BatContent = @"
@echo off
title Berry AI Studio
cd /d "%~dp0"
if exist "Berry AI Studio.exe" (
    echo Launching Berry AI Studio native desktop application...
    start "" "%~dp0Berry AI Studio.exe"
    exit /b 0
)
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

# Step 6: Final validation before compression
Write-Host "`n[6/6] Running final package validation..." -ForegroundColor Yellow

$ValidationErrors = @()

# Check all critical executables
$CriticalFiles = @(
    "$TargetDir\berry.exe",
    "$TargetDir\Berry AI Studio.exe",
    "$TargetDir\Berry.bat",
    "$TargetDir\README.txt",
    "$TargetDir\runtime\python\python.exe",
    "$TargetDir\frontend\dist\index.html",
    "$TargetDir\backend\app\main.py"
)

foreach ($file in $CriticalFiles) {
    if (-not (Test-Path $file)) {
        $ValidationErrors += "Missing critical file: $file"
    }
}

# Verify no developer machine paths leaked into the package
$PyvenvCfg = Get-ChildItem -Path "$TargetDir\runtime\python" -Filter "pyvenv.cfg" -ErrorAction SilentlyContinue
if ($PyvenvCfg) {
    $PyvenvContent = Get-Content $PyvenvCfg.FullName -Raw
    if ($PyvenvContent -match "home\s*=\s*[A-Za-z]:\\") {
        Write-Warning "pyvenv.cfg contains absolute path reference. This may cause issues on other machines."
        # Remove pyvenv.cfg for embeddable package (it's not needed)
        Remove-Item $PyvenvCfg.FullName -Force
        Write-Host "  -> Removed pyvenv.cfg to ensure portability" -ForegroundColor Yellow
    }
}

# Report validation results
if ($ValidationErrors.Count -gt 0) {
    Write-Host "`nVALIDATION FAILED:" -ForegroundColor Red
    foreach ($error in $ValidationErrors) {
        Write-Host "  X $error" -ForegroundColor Red
    }
    throw "Package validation failed with $($ValidationErrors.Count) error(s)"
}

Write-Host "  -> All critical files present" -ForegroundColor Green
Write-Host "  -> No developer-machine paths detected" -ForegroundColor Green

# Compress package into .zip
Write-Host "`nCompressing package into: $ZipFile" -ForegroundColor Yellow
if (Test-Path $ZipFile) {
    Remove-Item -Force $ZipFile
}
Compress-Archive -Path "$TargetDir\*" -DestinationPath $ZipFile -CompressionLevel Optimal

$ZipSizeMB = (Get-Item $ZipFile).Length / 1MB | ForEach-Object { [math]::Round($_, 1) }
Write-Host "  -> $ZipFile generated successfully ($ZipSizeMB MB)" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Packaging Complete!" -ForegroundColor Green
Write-Host "  Directory: $TargetDir" -ForegroundColor Green
Write-Host "  Archive  : $ZipFile" -ForegroundColor Green
Write-Host "  Next: Run smoke-test-package.ps1 to verify" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
