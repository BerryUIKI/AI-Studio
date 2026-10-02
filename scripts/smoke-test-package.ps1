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
Write-Host "`n[Check 1/4] Verifying artifact existence..." -ForegroundColor Yellow
if (-not (Test-Path $PackageDir)) {
    throw "Package directory does not exist: $PackageDir. Run package-windows-release.ps1 first."
}
if (-not (Test-Path $ZipFile)) {
    throw "Package zip file does not exist: $ZipFile"
}
Write-Host "  -> Directory and Zip archive confirmed present." -ForegroundColor Green

# Check 2: Core files existence
Write-Host "`n[Check 2/4] Verifying essential bundle files..." -ForegroundColor Yellow
$PythonExe = if (Test-Path "$PackageDir\runtime\python\Scripts\python.exe") {
    "$PackageDir\runtime\python\Scripts\python.exe"
} else {
    "$PackageDir\runtime\python\python.exe"
}

$RequiredFiles = @(
    "$PackageDir\berry.exe",
    "$PackageDir\Berry.bat",
    "$PackageDir\README.txt",
    $PythonExe,
    "$PackageDir\frontend\dist\index.html",
    "$PackageDir\backend\app\main.py"
)

foreach ($file in $RequiredFiles) {
    if (-not (Test-Path $file)) {
        throw "Missing required bundle file: $file"
    }
    Write-Host "  -> Found $(Split-Path $file -Leaf)" -ForegroundColor Green
}

# Check 3: Invoking launcher --help with isolated PATH
Write-Host "`n[Check 3/4] Testing berry.exe CLI in PATH-sanitized environment..." -ForegroundColor Yellow
$OriginalPath = $env:PATH
try {
    # Sanitize PATH to remove host Python, Git, and Node.js
    $SanitizedPath = ($env:PATH -split ';' | Where-Object { 
        $_ -notmatch "Python" -and $_ -notmatch "nodejs" -and $_ -notmatch "npm" -and $_ -notmatch "pnpm" -and $_ -notmatch "Git"
    }) -join ';'
    $env:PATH = $SanitizedPath

    $HelpOutput = (& "$PackageDir\berry.exe" --help) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "berry.exe --help failed with exit code $LASTEXITCODE"
    }
    if ($HelpOutput -notmatch "Berry AI Studio") {
        throw "Unexpected help output from berry.exe: $HelpOutput"
    }
    Write-Host "  -> berry.exe --help succeeded with exit code 0" -ForegroundColor Green
} finally {
    $env:PATH = $OriginalPath
}

# Check 4: Verifying bundled python runtime functionality
Write-Host "`n[Check 4/4] Verifying bundled Python hermetic execution..." -ForegroundColor Yellow
$PyVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) {
    throw "Bundled python.exe failed to execute"
}
Write-Host "  -> Bundled Python executable runs successfully (Python $PyVersion)" -ForegroundColor Green

$PyFastAPI = & $PythonExe -c "import fastapi, pydantic; print('OK')"
if ($LASTEXITCODE -ne 0 -or $PyFastAPI -notmatch "OK") {
    throw "Bundled python.exe failed to import backend dependencies"
}
Write-Host "  -> Bundled Python environment contains required dependencies (fastapi, pydantic)" -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  All 4 Package Smoke Tests PASSED!" -ForegroundColor Green
Write-Host "  Distribution is verified clean-machine ready (L01 satisfied)." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
