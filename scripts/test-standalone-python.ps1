# Berry AI Studio - Standalone Python Runtime Test
# Verifies that the prepared Python runtime is complete and self-contained.

param (
    [string]$PythonDir = "$PSScriptRoot\..\runtime\python-standalone"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Standalone Python Runtime Test" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Test 1: Python executable exists
Write-Host "`n[Test 1/5] Verifying Python executable exists..." -ForegroundColor Yellow
$PythonExe = "$PythonDir\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found at $PythonExe. Run prepare-standalone-python.ps1 first."
}
Write-Host "  -> Python executable found" -ForegroundColor Green

# Test 2: Python runs and reports version
Write-Host "`n[Test 2/5] Testing Python execution..." -ForegroundColor Yellow
$PyVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Python execution failed: $PyVersion"
}
Write-Host "  -> Python version: $PyVersion" -ForegroundColor Green

# Test 3: Verify sys.prefix points to standalone directory
Write-Host "`n[Test 3/5] Verifying Python is self-contained..." -ForegroundColor Yellow
$SysPrefix = & $PythonExe -c "import sys, os; print(os.path.normpath(sys.prefix))" 2>&1
$ExpectedPrefix = (Resolve-Path $PythonDir).Path

if ($LASTEXITCODE -ne 0) {
    throw "Failed to get sys.prefix: $SysPrefix"
}

# Normalize paths for comparison
$SysPrefix = $SysPrefix.Trim().TrimEnd('\')
$ExpectedPrefix = $ExpectedPrefix.TrimEnd('\')

if ($SysPrefix -like "*$ExpectedPrefix*" -or $ExpectedPrefix -like "*$SysPrefix*") {
    Write-Host "  -> sys.prefix points to standalone directory" -ForegroundColor Green
    Write-Host "    sys.prefix: $SysPrefix" -ForegroundColor Gray
} else {
    throw "sys.prefix points to external location: $SysPrefix (expected within $ExpectedPrefix)"
}

# Test 4: Verify pip is installed
Write-Host "`n[Test 4/5] Verifying pip installation..." -ForegroundColor Yellow
$PipVersion = & $PythonExe -m pip --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "pip is not installed or not functional: $PipVersion"
}
Write-Host "  -> pip installed: $PipVersion" -ForegroundColor Green

# Test 5: Verify backend dependencies
Write-Host "`n[Test 5/5] Verifying backend dependencies..." -ForegroundColor Yellow
$RequiredPackages = @("fastapi", "pydantic", "uvicorn", "httpx", "pytest", "aiosqlite", "Pillow")
$MissingPackages = @()

foreach ($pkg in $RequiredPackages) {
    $TestImport = & $PythonExe -c "import $($pkg.ToLower()); print('OK')" 2>&1
    if ($LASTEXITCODE -ne 0 -or $TestImport -notmatch "OK") {
        $MissingPackages += $pkg
        Write-Host "  X Missing: $pkg" -ForegroundColor Red
    } else {
        Write-Host "  -> Found: $pkg" -ForegroundColor Green
    }
}

if ($MissingPackages.Count -gt 0) {
    throw "Missing required packages: $($MissingPackages -join ', ')"
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Standalone Python Runtime Test PASSED!" -ForegroundColor Green
Write-Host "  Runtime is complete and self-contained." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
