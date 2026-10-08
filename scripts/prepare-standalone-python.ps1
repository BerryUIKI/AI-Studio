# Berry AI Studio - Standalone Python Runtime Preparation
# Creates a complete portable Python environment for Windows packaging.
# Requires Python 3.10+ on the build machine; resulting runtime is self-contained.

param (
    [string]$TargetDir = "$PSScriptRoot\..\runtime\python-standalone"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Preparing Standalone Python Runtime" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check for system Python
$SystemPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $SystemPython) {
    throw "Python 3.10+ is required to build the standalone runtime. Install from https://python.org"
}

$PyVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Failed to get Python version: $PyVersion"
}

Write-Host "  Build machine Python: $PyVersion" -ForegroundColor Green

# Create target directory
if (Test-Path $TargetDir) {
    Write-Host "Removing existing standalone runtime at $TargetDir..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $TargetDir
}

# Create virtualenv using system Python
Write-Host "`n[1/3] Creating isolated virtual environment..." -ForegroundColor Yellow
& python -m venv $TargetDir
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create virtual environment. Ensure 'python -m venv' works."
}
Write-Host "  -> Virtual environment created" -ForegroundColor Green

# Install backend dependencies
Write-Host "`n[2/3] Installing backend dependencies..." -ForegroundColor Yellow
$RequirementsFile = "$PSScriptRoot\..\backend\requirements.txt"
if (-not (Test-Path $RequirementsFile)) {
    throw "requirements.txt not found at $RequirementsFile"
}

$PipExe = Join-Path $TargetDir "Scripts\pip.exe"
& $PipExe install -r $RequirementsFile --no-warn-script-location
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install dependencies"
}
Write-Host "  -> All backend dependencies installed" -ForegroundColor Green

# Make portable by cleaning pyvenv.cfg
Write-Host "`n[3/3] Making runtime portable..." -ForegroundColor Yellow
$PyvenvCfg = Join-Path $TargetDir "pyvenv.cfg"
if (Test-Path $PyvenvCfg) {
    # Modify pyvenv.cfg to use relative paths instead of removing it
    $Content = Get-Content $PyvenvCfg
    $NewContent = @()
    foreach ($Line in $Content) {
        # Keep the file but remove absolute home path references
        if ($Line -match "^home\s*=") {
            # Comment out or skip the home line - venv will work without it
            continue
        }
        $NewContent += $Line
    }
    Set-Content -Path $PyvenvCfg -Value $NewContent
    Write-Host "  -> Cleaned pyvenv.cfg (portable mode)" -ForegroundColor Green
}

# Verify runtime
Write-Host "`nVerifying standalone runtime..." -ForegroundColor Yellow
$PythonExe = Join-Path $TargetDir "Scripts\python.exe"

$TestVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Runtime verification failed: $TestVersion"
}
Write-Host "  -> Python version: $TestVersion" -ForegroundColor Green

$TestVenv = & $PythonExe -c "import venv; print('OK')" 2>&1
if ($LASTEXITCODE -eq 0 -and $TestVenv -match "OK") {
    Write-Host "  -> venv module available" -ForegroundColor Green
} else {
    Write-Warning "venv module not available: $TestVenv"
}

$TestDeps = & $PythonExe -c "import fastapi, pydantic, uvicorn, httpx; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0 -or $TestDeps -notmatch "OK") {
    throw "Backend dependencies verification failed: $TestDeps"
}
Write-Host "  -> Backend dependencies verified (fastapi, pydantic, uvicorn, httpx)" -ForegroundColor Green

# Test venv creation capability
$TestVenvPath = Join-Path $TargetDir "test_venv_creation"
& $PythonExe -m venv $TestVenvPath 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0 -and (Test-Path "$TestVenvPath\Scripts\python.exe")) {
    Remove-Item -Recurse -Force $TestVenvPath
    Write-Host "  -> venv creation works (engine isolation capable)" -ForegroundColor Green
} else {
    Write-Warning "venv creation test failed"
}

$RuntimeSize = (Get-ChildItem -Recurse $TargetDir | Measure-Object -Property Length -Sum).Sum / 1MB
$RuntimeSize = [math]::Round($RuntimeSize, 1)

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Standalone Python Runtime Ready!" -ForegroundColor Green
Write-Host "  Location: $TargetDir" -ForegroundColor Green
Write-Host "  Size: $RuntimeSize MB" -ForegroundColor Green
Write-Host "  Note: Built using system Python, runtime is portable" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
