# Berry AI Studio PowerShell Launcher & Environment Manager

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$LauncherRelease = Join-Path $RootDir "launcher\target\release\berry.exe"
$LauncherDebug = Join-Path $RootDir "launcher\target\debug\berry.exe"
$CargoToml = Join-Path $RootDir "launcher\Cargo.toml"

# 1. Check for compiled Rust launcher binary
if (Test-Path $LauncherRelease) {
    & $LauncherRelease $args
    exit $LASTEXITCODE
}

if (Test-Path $LauncherDebug) {
    & $LauncherDebug $args
    exit $LASTEXITCODE
}

# 2. Check for Cargo to compile and run launcher
$Cargo = Get-Command cargo -ErrorAction SilentlyContinue
if ($Cargo) {
    Write-Host "[*] Building Berry AI Studio Rust launcher..." -ForegroundColor Cyan
    cargo run --release --manifest-path $CargoToml -- $args
    exit $LASTEXITCODE
}

# 3. Standalone Python bootstrap fallback
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              Berry AI Studio (Windows)                 " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$BackendDir = Join-Path $RootDir "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

$HostPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $HostPython) {
    Write-Error "Python 3.10+ was not found on your system PATH. Please install Python 3.10+ from python.org"
    exit 1
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "[1/3] Initializing isolated virtual environment in $VenvDir..." -ForegroundColor Yellow
    python -m venv $VenvDir
    Write-Host "[2/3] Installing dependencies..." -ForegroundColor Yellow
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")
} else {
    Write-Host "[1/3] Sandboxed virtual environment verified." -ForegroundColor Green
}

Write-Host "[2/3] Starting Berry AI Studio on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Set-Location $BackendDir
$proc = Start-Process -FilePath $PythonExe -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -PassThru

# Wait for health probe before opening browser
Write-Host "[3/3] Probing readiness..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 1000
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1
        if ($resp.status -eq "ok") {
            $ready = $true
            break
        }
    } catch {}
}

if ($ready) {
    Write-Host "[*] Opening creative workspace in default browser..." -ForegroundColor Green
    Start-Process "http://127.0.0.1:8000"
} else {
    Write-Warning "Backend did not respond within 30 seconds."
}

$proc.WaitForExit()
