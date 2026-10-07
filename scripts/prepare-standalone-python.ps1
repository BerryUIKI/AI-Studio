# Berry AI Studio - Standalone Python Runtime Preparation
# Downloads and configures a complete embeddable Python distribution for Windows packaging.

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

# Download Python embeddable package
$PythonMajorMinor = $PythonVersion.Substring(0, $PythonVersion.LastIndexOf('.'))
$DownloadUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$ZipFile = Join-Path $env:TEMP "python-$PythonVersion-embed-amd64.zip"

Write-Host "`n[1/5] Downloading Python $PythonVersion embeddable package..." -ForegroundColor Yellow
Write-Host "  URL: $DownloadUrl" -ForegroundColor Gray

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipFile -UseBasicParsing
    Write-Host "  -> Downloaded to: $ZipFile" -ForegroundColor Green
} catch {
    throw "Failed to download Python embeddable package: $_"
}

# Extract Python
Write-Host "`n[2/5] Extracting Python runtime..." -ForegroundColor Yellow
Expand-Archive -Path $ZipFile -DestinationPath $TargetDir -Force
Remove-Item $ZipFile -Force
Write-Host "  -> Extracted to: $TargetDir" -ForegroundColor Green

# Download and install pip
Write-Host "`n[3/5] Installing pip into standalone runtime..." -ForegroundColor Yellow
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPipFile = Join-Path $TargetDir "get-pip.py"

try {
    Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipFile -UseBasicParsing
    Write-Host "  -> Downloaded get-pip.py" -ForegroundColor Green
} catch {
    throw "Failed to download get-pip.py: $_"
}

# Uncomment import site in python*._pth to enable pip
$PthFile = Get-ChildItem -Path $TargetDir -Filter "python*._pth" | Select-Object -First 1
if ($PthFile) {
    Write-Host "  -> Enabling site-packages in $($PthFile.Name)..." -ForegroundColor Gray
    $PthContent = Get-Content $PthFile.FullName
    $PthContent = $PthContent -replace '^#import site', 'import site'
    $PthContent = $PthContent + "`nLib/site-packages"
    Set-Content -Path $PthFile.FullName -Value $PthContent
    Write-Host "  -> Enabled site-packages support" -ForegroundColor Green
}

# Install pip
Push-Location $TargetDir
try {
    & ".\python.exe" "get-pip.py" --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw "pip installation failed" }
    Remove-Item "get-pip.py" -Force
    Write-Host "  -> pip installed successfully" -ForegroundColor Green
} finally {
    Pop-Location
}

# Install backend dependencies
Write-Host "`n[4/5] Installing backend dependencies..." -ForegroundColor Yellow
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

# Verify installation
Write-Host "`n[5/5] Verifying standalone runtime..." -ForegroundColor Yellow
Push-Location $TargetDir
try {
    $PyVersion = & ".\python.exe" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    if ($LASTEXITCODE -ne 0) { throw "Python verification failed" }
    Write-Host "  -> Python version: $PyVersion" -ForegroundColor Green

    $TestImports = & ".\python.exe" -c "import fastapi, pydantic, uvicorn, httpx; print('OK')"
    if ($LASTEXITCODE -ne 0 -or $TestImports -notmatch "OK") {
        throw "Required dependencies not found"
    }
    Write-Host "  -> Backend dependencies verified (fastapi, pydantic, uvicorn, httpx)" -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Standalone Python Runtime Ready!" -ForegroundColor Green
Write-Host "  Location: $TargetDir" -ForegroundColor Green
Write-Host "  Size: $((Get-ChildItem -Recurse $TargetDir | Measure-Object -Property Length -Sum).Sum / 1MB | ForEach-Object { [math]::Round($_, 1) }) MB" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
