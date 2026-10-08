# Berry AI Studio - Standalone Python Runtime Preparation
# Downloads and configures a complete redistributable Python distribution for Windows packaging.
# Uses embeddable package + manual venv module addition for complete functionality.

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
$EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$EmbedZip = Join-Path $env:TEMP "python-$PythonVersion-embed-amd64.zip"

Write-Host "`n[1/6] Downloading Python $PythonVersion embeddable package..." -ForegroundColor Yellow
Write-Host "  URL: $EmbedUrl" -ForegroundColor Gray

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $EmbedUrl -OutFile $EmbedZip -UseBasicParsing
    Write-Host "  -> Downloaded embeddable package" -ForegroundColor Green
} catch {
    throw "Failed to download Python embeddable package: $_"
}

# Extract embeddable Python
Write-Host "`n[2/6] Extracting Python runtime..." -ForegroundColor Yellow
Expand-Archive -Path $EmbedZip -DestinationPath $TargetDir -Force
Remove-Item $EmbedZip -Force
Write-Host "  -> Extracted to: $TargetDir" -ForegroundColor Green

# Download full installer to extract venv module
Write-Host "`n[3/6] Downloading full installer for venv module..." -ForegroundColor Yellow
$InstallerUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
$InstallerFile = Join-Path $env:TEMP "python-installer-$(Get-Random).exe"

try {
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $InstallerFile -UseBasicParsing
    Write-Host "  -> Downloaded full installer" -ForegroundColor Green
} catch {
    throw "Failed to download Python installer: $_"
}

# Extract venv and ensurepip from installer using administrative layout
$TempExtract = Join-Path $env:TEMP "python_extract_$PythonVersion"
if (Test-Path $TempExtract) {
    Remove-Item -Recurse -Force $TempExtract
}
New-Item -ItemType Directory -Path $TempExtract -Force | Out-Null

Write-Host "  -> Extracting venv module from installer..." -ForegroundColor Gray
try {
    # Extract using admin layout
    $Process = Start-Process -FilePath $InstallerFile -ArgumentList "/layout `"$TempExtract`" /quiet" -Wait -PassThru -NoNewWindow

    if ($Process.ExitCode -ne 0) {
        # Try 7z extraction as fallback
        $7z = Get-Command 7z -ErrorAction SilentlyContinue
        if ($7z) {
            & 7z x $InstallerFile "-o$TempExtract" -y | Out-Null
        }
    }

    # Find and copy venv from extracted files
    $VenvSource = Get-ChildItem -Path $TempExtract -Recurse -Directory -Filter "venv" -ErrorAction SilentlyContinue | Select-Object -First 1
    $EnsurepipSource = Get-ChildItem -Path $TempExtract -Recurse -Directory -Filter "ensurepip" -ErrorAction SilentlyContinue | Select-Object -First 1

    # Create Lib directory in target if needed
    $TargetLib = Join-Path $TargetDir "Lib"
    if (-not (Test-Path $TargetLib)) {
        New-Item -ItemType Directory -Path $TargetLib -Force | Out-Null
    }

    if ($VenvSource) {
        Copy-Item -Recurse $VenvSource.FullName -Destination $TargetLib -Force
        Write-Host "  -> Copied venv module" -ForegroundColor Green
    } else {
        Write-Warning "Could not extract venv module from installer"
    }

    if ($EnsurepipSource) {
        Copy-Item -Recurse $EnsurepipSource.FullName -Destination $TargetLib -Force
        Write-Host "  -> Copied ensurepip module" -ForegroundColor Green
    }

    Remove-Item -Recurse -Force $TempExtract -ErrorAction SilentlyContinue
    Remove-Item $InstallerFile -Force
} catch {
    Write-Warning "Failed to extract venv from installer: $_"
    Remove-Item $InstallerFile -Force -ErrorAction SilentlyContinue
}

# Enable site-packages in embeddable Python
Write-Host "`n[4/6] Configuring embeddable Python..." -ForegroundColor Yellow
$PthFile = Get-ChildItem -Path $TargetDir -Filter "python*._pth" | Select-Object -First 1
if ($PthFile) {
    $PthContent = Get-Content $PthFile.FullName
    $PthContent = $PthContent -replace '^#import site', 'import site'
    $PthContent = $PthContent + "`nLib"
    $PthContent = $PthContent + "`nLib/site-packages"
    Set-Content -Path $PthFile.FullName -Value $PthContent
    Write-Host "  -> Enabled site-packages support" -ForegroundColor Green
}

# Install pip
Write-Host "`n[5/6] Installing pip..." -ForegroundColor Yellow
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPipFile = Join-Path $TargetDir "get-pip.py"

try {
    Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipFile -UseBasicParsing

    Push-Location $TargetDir
    try {
        & ".\python.exe" "get-pip.py" --no-warn-script-location
        if ($LASTEXITCODE -ne 0) { throw "pip installation failed" }
        Remove-Item "get-pip.py" -Force
        Write-Host "  -> pip installed successfully" -ForegroundColor Green
    } finally {
        Pop-Location
    }
} catch {
    throw "Failed to install pip: $_"
}

# Install backend dependencies
Write-Host "`n[6/6] Installing backend dependencies..." -ForegroundColor Yellow
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

    # Test venv module
    $VenvTest = & ".\python.exe" -c "import venv; print('OK')" 2>&1
    if ($LASTEXITCODE -eq 0 -and $VenvTest -match "OK") {
        Write-Host "  -> venv module available" -ForegroundColor Green

        # Test venv creation
        $TestVenv = "test_venv_capability"
        & ".\python.exe" -m venv $TestVenv 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0 -and (Test-Path "$TestVenv\Scripts\python.exe")) {
            Remove-Item -Recurse -Force $TestVenv
            Write-Host "  -> venv creation works" -ForegroundColor Green
        } else {
            Write-Warning "venv module imported but creation failed - may require system Python"
        }
    } else {
        Write-Warning "venv module not available: $VenvTest"
    }

    $TestImports = & ".\python.exe" -c "import fastapi, pydantic, uvicorn, httpx; print('OK')" 2>&1
    if ($LASTEXITCODE -ne 0 -or $TestImports -notmatch "OK") {
        throw "Required dependencies not found: $TestImports"
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
