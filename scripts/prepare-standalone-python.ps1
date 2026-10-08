# Berry AI Studio - Standalone Python Runtime Preparation
# Downloads and configures a complete redistributable Python distribution for Windows packaging.
# Uses the official Windows installer in portable mode to get a complete runtime with venv support.

param (
    [string]$PythonVersion = "3.11.9",
    [string]$TargetDir = "$PSScriptRoot\..\runtime\python-standalone"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Preparing Standalone Python Runtime" -ForegroundColor Cyan
Write-Host "  Version: $PythonVersion" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Create target directory
if (Test-Path $TargetDir) {
    Write-Host "Removing existing standalone runtime at $TargetDir..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $TargetDir
}
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null

# Download Python installer (includes venv, pip, full stdlib)
$PythonMajorMinor = $PythonVersion.Substring(0, $PythonVersion.LastIndexOf('.'))
$InstallerUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
$InstallerFile = Join-Path $env:TEMP "python-$PythonVersion-amd64.exe"

Write-Host "`n[1/4] Downloading Python $PythonVersion installer..." -ForegroundColor Yellow
Write-Host "  URL: $InstallerUrl" -ForegroundColor Gray

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $InstallerFile -UseBasicParsing
    Write-Host "  -> Downloaded to: $InstallerFile" -ForegroundColor Green
} catch {
    throw "Failed to download Python installer: $_"
}

# Extract Python using installer in "TargetDir" mode (portable installation)
Write-Host "`n[2/4] Extracting Python runtime (this may take 2-3 minutes)..." -ForegroundColor Yellow
Write-Host "  -> Running installer with TargetDir=$TargetDir" -ForegroundColor Gray

try {
    # Use /passive mode with TargetDir and specific options
    # InstallAllUsers=0 and no system modifications for portable install
    $InstallArgs = "/passive TargetDir=`"$TargetDir`" Include_pip=1 Include_test=0 Include_tcltk=0 Include_launcher=0 InstallAllUsers=0 PrependPath=0 Shortcuts=0 AssociateFiles=0"

    $Process = Start-Process -FilePath $InstallerFile -ArgumentList $InstallArgs -Wait -PassThru -NoNewWindow

    if ($Process.ExitCode -ne 0) {
        throw "Python installer failed with exit code $($Process.ExitCode)"
    }

    Remove-Item $InstallerFile -Force
    Write-Host "  -> Extracted to: $TargetDir" -ForegroundColor Green
} catch {
    throw "Failed to extract Python installer: $_"
}

# Verify extraction includes necessary components
Write-Host "`n[3/4] Verifying runtime components..." -ForegroundColor Yellow

$PythonExe = Join-Path $TargetDir "python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found at $PythonExe after extraction"
}

# Check for venv module (critical for engine installation)
Push-Location $TargetDir
try {
    $VenvCheck = & ".\python.exe" -c "import venv; print('OK')" 2>&1
    if ($LASTEXITCODE -ne 0 -or $VenvCheck -notmatch "OK") {
        throw "venv module not available in extracted runtime"
    }
    Write-Host "  -> venv module available" -ForegroundColor Green

    # Check for pip
    $PipCheck = & ".\python.exe" -m pip --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "pip not available in extracted runtime"
    }
    Write-Host "  -> pip available" -ForegroundColor Green
} finally {
    Pop-Location
}

# Install backend dependencies
Write-Host "`n[4/4] Installing backend dependencies..." -ForegroundColor Yellow
$RequirementsFile = "$PSScriptRoot\..\backend\requirements.txt"
if (-not (Test-Path $RequirementsFile)) {
    throw "requirements.txt not found at $RequirementsFile"
}

Push-Location $TargetDir
try {
    & ".\python.exe" -m pip install -r $RequirementsFile --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    Write-Host "  -> All backend dependencies installed" -ForegroundColor Green
} finally {
    Pop-Location
}

# Final verification
Write-Host "`nVerifying standalone runtime..." -ForegroundColor Yellow
Push-Location $TargetDir
try {
    $PyVersion = & ".\python.exe" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    if ($LASTEXITCODE -ne 0) { throw "Python verification failed" }
    Write-Host "  -> Python version: $PyVersion" -ForegroundColor Green

    # Test venv creation capability
    $TestVenv = "test_venv_capability"
    & ".\python.exe" -m venv $TestVenv 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0 -and (Test-Path "$TestVenv\Scripts\python.exe")) {
        Remove-Item -Recurse -Force $TestVenv
        Write-Host "  -> venv creation works" -ForegroundColor Green
    } else {
        throw "venv creation test failed"
    }

    $TestImports = & ".\python.exe" -c "import fastapi, pydantic, uvicorn, httpx, venv; print('OK')" 2>&1
    if ($LASTEXITCODE -ne 0 -or $TestImports -notmatch "OK") {
        throw "Required dependencies not found: $TestImports"
    }
    Write-Host "  -> Backend dependencies verified (fastapi, pydantic, uvicorn, httpx, venv)" -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Standalone Python Runtime Ready!" -ForegroundColor Green
Write-Host "  Location: $TargetDir" -ForegroundColor Green
Write-Host "  Size: $((Get-ChildItem -Recurse $TargetDir | Measure-Object -Property Length -Sum).Sum / 1MB | ForEach-Object { [math]::Round($_, 1) }) MB" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
