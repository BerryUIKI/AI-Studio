# Berry AI Studio - Automated Windows Package Smoke Test (L01 Verification)
# Validates that the packaged distribution contains all assets and runs with sanitized PATH.

param (
    [string]$Version = "0.1.0",
    [string]$OutputDir = "$PSScriptRoot\..\dist"
)

$ErrorActionPreference = "Stop"
$DistName = "Berry-AI-Studio-v$Version-windows-x64"
$PackageDir = Join-Path $OutputDir $DistName
$ZipFile = Join-Path $OutputDir "$DistName.zip"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Berry AI Studio - Windows Package Smoke Test" -ForegroundColor Cyan
Write-Host "  Testing target: $PackageDir" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check 1: Directory and Zip existence
Write-Host "`n[Check 1/6] Verifying artifact existence..." -ForegroundColor Yellow
if (-not (Test-Path $PackageDir)) {
    throw "Package directory does not exist: $PackageDir. Run package-windows-release.ps1 first."
}
if (-not (Test-Path $ZipFile)) {
    throw "Package zip file does not exist: $ZipFile"
}
Write-Host "  -> Directory and Zip archive confirmed present." -ForegroundColor Green

# Check 2: Core files existence
Write-Host "`n[Check 2/6] Verifying essential bundle files..." -ForegroundColor Yellow
$PythonExe = "$PackageDir\runtime\python\python.exe"

$RequiredFiles = @(
    "$PackageDir\berry.exe",
    "$PackageDir\Berry AI Studio.exe",
    "$PackageDir\Berry.bat",
    "$PackageDir\README.txt",
    $PythonExe,
    "$PackageDir\frontend\dist\index.html",
    "$PackageDir\backend\app\main.py"
)

$MissingFiles = @()
foreach ($file in $RequiredFiles) {
    if (-not (Test-Path $file)) {
        $MissingFiles += $file
        Write-Host "  X Missing: $(Split-Path $file -Leaf)" -ForegroundColor Red
    } else {
        Write-Host "  -> Found $(Split-Path $file -Leaf)" -ForegroundColor Green
    }
}

if ($MissingFiles.Count -gt 0) {
    throw "SMOKE TEST FAILED: $($MissingFiles.Count) required file(s) missing"
}

# Check 3: No developer-machine paths in runtime
Write-Host "`n[Check 3/6] Verifying no developer-machine path leakage..." -ForegroundColor Yellow

$PathLeakageFound = $false

# Check for pyvenv.cfg (should not exist in embeddable package)
$PyvenvCfg = Get-ChildItem -Path "$PackageDir\runtime\python" -Filter "pyvenv.cfg" -Recurse -ErrorAction SilentlyContinue
if ($PyvenvCfg) {
    $PyvenvContent = Get-Content $PyvenvCfg.FullName -Raw
    if ($PyvenvContent -match "home\s*=\s*[A-Za-z]:\\") {
        Write-Host "  X pyvenv.cfg contains absolute developer-machine paths" -ForegroundColor Red
        Write-Host "    File: $($PyvenvCfg.FullName)" -ForegroundColor Gray
        $PathLeakageFound = $true
    }
}

# Check Python executable for base_prefix leakage
$BasePrefix = & $PythonExe -c "import sys; print(sys.base_prefix)" 2>&1
if ($LASTEXITCODE -eq 0 -and $BasePrefix -match "[A-Za-z]:\\" -and $BasePrefix -notmatch [regex]::Escape($PackageDir)) {
    Write-Host "  X Python sys.base_prefix points outside package: $BasePrefix" -ForegroundColor Red
    $PathLeakageFound = $true
}

if ($PathLeakageFound) {
    throw "SMOKE TEST FAILED: Developer-machine paths detected in package"
}
Write-Host "  -> No developer-machine paths detected" -ForegroundColor Green

# Check 4: Invoking launcher --help with isolated PATH
Write-Host "`n[Check 4/6] Testing berry.exe CLI in PATH-sanitized environment..." -ForegroundColor Yellow
$OriginalPath = $env:PATH
try {
    # Sanitize PATH to remove host Python, Git, and Node.js
    $SanitizedPath = ($env:PATH -split ';' | Where-Object {
        $_ -notmatch "Python" -and
        $_ -notmatch "nodejs" -and
        $_ -notmatch "npm" -and
        $_ -notmatch "pnpm" -and
        $_ -notmatch "Git" -and
        $_ -notmatch "Anaconda" -and
        $_ -notmatch "Miniconda"
    }) -join ';'
    $env:PATH = $SanitizedPath

    $HelpOutput = (& "$PackageDir\berry.exe" --help 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "berry.exe --help failed with exit code $LASTEXITCODE. Output: $HelpOutput"
    }
    if ($HelpOutput -notmatch "Berry AI Studio|berry\.exe|Usage") {
        throw "Unexpected help output from berry.exe: $HelpOutput"
    }
    Write-Host "  -> berry.exe --help succeeded in clean environment" -ForegroundColor Green
} finally {
    $env:PATH = $OriginalPath
}

# Check 5: Verifying bundled python runtime functionality
Write-Host "`n[Check 5/6] Verifying bundled Python hermetic execution..." -ForegroundColor Yellow

# Test Python version
$PyVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Bundled python.exe failed to execute. Error: $PyVersion"
}
Write-Host "  -> Bundled Python executable runs successfully (Python $PyVersion)" -ForegroundColor Green

# Test backend dependencies
# Test backend dependencies
$PyFastAPI = & $PythonExe -c "import fastapi, pydantic, uvicorn, httpx; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0 -or $PyFastAPI -notmatch "OK") {
    throw "Bundled python.exe failed to import backend dependencies. Error: $PyFastAPI"
}
Write-Host "  -> Backend dependencies verified (fastapi, pydantic, uvicorn, httpx)" -ForegroundColor Green

# Test venv module (required for engine installation)
$PyVenv = & $PythonExe -c "import venv; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0 -or $PyVenv -notmatch "OK") {
    throw "Bundled python.exe missing venv module. Engine installation will fail. Error: $PyVenv"
}
Write-Host "  -> venv module available for engine isolation" -ForegroundColor Green

# Test app.main import (backend startup capability)
$PyAppMain = & $PythonExe -c "import sys; sys.path.insert(0, r'$PackageDir\backend'); import app.main; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0 -or $PyAppMain -notmatch "OK") {
    throw "Bundled python.exe cannot import app.main. Backend startup will fail. Error: $PyAppMain"
}
Write-Host "  -> app.main import successful (backend startup capable)" -ForegroundColor Green

# Test sys.executable points to bundled Python
$SysExecutable = & $PythonExe -c "import sys; print(sys.executable)" 2>&1
if ($LASTEXITCODE -eq 0) {
    $ExpectedPath = Join-Path $PackageDir "runtime\python\python.exe"
    if ($SysExecutable -notlike "*$PackageDir*") {
        Write-Warning "sys.executable may point outside package: $SysExecutable"
    } else {
        Write-Host "  -> sys.executable correctly points to bundled Python" -ForegroundColor Green
    }
}

# Check 6: Verify portable Git if bundled
Write-Host "`n[Check 6/7] Verifying bundled portable Git..." -ForegroundColor Yellow
$PortableGitExe = "$PackageDir\runtime\git\cmd\git.exe"
if (-not (Test-Path $PortableGitExe)) {
    throw "REQUIRED: Portable Git not found at $PortableGitExe. Engine installation will fail."
}

try {
    $GitVersion = & $PortableGitExe --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Bundled Git execution failed with exit code $LASTEXITCODE : $GitVersion"
    }
    if ($GitVersion -notmatch "git version") {
        throw "Bundled Git returned unexpected output: $GitVersion"
    }
    Write-Host "  -> Portable Git bundled and functional: $($GitVersion -replace '[\r\n]', '')" -ForegroundColor Green
} catch {
    throw "REQUIRED: Bundled Git is broken or incomplete: $_"
}

# Check 7: Test venv creation with bundled Python
Write-Host "`n[Check 7/7] Testing isolated venv creation capability..." -ForegroundColor Yellow
$TestVenvPath = "$PackageDir\test_venv_smoke"
try {
    & $PythonExe -m venv $TestVenvPath 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "venv creation failed with exit code $LASTEXITCODE"
    }

    $VenvPython = "$TestVenvPath\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        throw "venv python.exe not created at $VenvPython"
    }

    # Test the venv Python works
    $VenvTest = & $VenvPython -c "import sys; print('OK')" 2>&1
    if ($LASTEXITCODE -ne 0 -or $VenvTest -notmatch "OK") {
        throw "venv Python execution failed: $VenvTest"
    }

    Write-Host "  -> venv creation successful (engine installation capable)" -ForegroundColor Green
} catch {
    throw "CRITICAL: venv creation failed. Engine installation will not work: $_"
} finally {
    if (Test-Path $TestVenvPath) {
        Remove-Item -Recurse -Force $TestVenvPath -ErrorAction SilentlyContinue
    }
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  All 7 Package Smoke Tests PASSED!" -ForegroundColor Green
Write-Host "  Distribution verified for clean-machine deployment." -ForegroundColor Green
Write-Host "`n  Verified capabilities:" -ForegroundColor Yellow
Write-Host "    - Self-contained Python runtime with venv support" -ForegroundColor Yellow
Write-Host "    - Backend startup (app.main import)" -ForegroundColor Yellow
Write-Host "    - Isolated engine environment creation" -ForegroundColor Yellow
Write-Host "    - Bundled Git for repository operations" -ForegroundColor Yellow
Write-Host "`n  NOTE: This is a host-machine test with PATH sanitization." -ForegroundColor Yellow
Write-Host "  Full L01 acceptance requires clean Windows VM verification:" -ForegroundColor Yellow
Write-Host "    - Extract on Windows VM without Python/Git/Node" -ForegroundColor Yellow
Write-Host "    - Run Berry.bat or berry.exe" -ForegroundColor Yellow
Write-Host "    - Verify startup, cloud onboarding, and safe exit" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
