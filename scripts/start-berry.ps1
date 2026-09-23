# Berry AI Studio PowerShell Launcher

$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              Berry AI Studio (Windows)                 " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

# 1. Check Python
$HostPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $HostPython) {
    Write-Error "Python 3.10+ was not found on your system PATH. Please install Python 3.10+ from python.org"
    exit 1
}

# 2. Check virtual environment
if (-not (Test-Path $PythonExe)) {
    Write-Host "[1/3] Initializing isolated virtual environment in $VenvDir..." -ForegroundColor Yellow
    python -m venv $VenvDir
    Write-Host "[2/3] Installing dependencies..." -ForegroundColor Yellow
    & $PythonExe -m pip install --upgrade pip
    & $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")
} else {
    Write-Host "[1/3] Sandboxed virtual environment verified." -ForegroundColor Green
}

# 3. Launch and open browser
Write-Host "[3/3] Starting Berry AI Studio on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:8000"

Set-Location $BackendDir
& $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
