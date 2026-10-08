# Host smoke evidence; clean Windows VM acceptance is a separate gate.
param (
    [string]$Version = "0.1.0",
    [string]$OutputDir = "$PSScriptRoot\..\dist"
)
$ErrorActionPreference = "Stop"
if ($Version -notmatch '^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$') { throw "Invalid package version." }
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
$DistName = "Berry-AI-Studio-v$Version-windows-x64"
$ZipFile = Join-Path $OutputDir "$DistName.zip"
if (-not (Test-Path -LiteralPath $ZipFile)) { throw "Missing package archive: $ZipFile" }
# Test the delivered zip after extraction to a different path, not the build staging tree.
$ProbeDir = Join-Path $OutputDir "package-smoke-$([guid]::NewGuid().ToString('N'))"
if (-not $ProbeDir.StartsWith("$OutputDir\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "Smoke extraction must stay inside the selected output directory."
}
$SavedPath = $env:PATH
try {
    Expand-Archive -LiteralPath $ZipFile -DestinationPath $ProbeDir
    $RequiredFiles = @(
        "berry.exe", "Berry AI Studio.exe", "Berry.bat", "README.txt",
        "runtime\python\python.exe", "runtime\git\cmd\git.exe",
        "frontend\dist\index.html", "backend\app\main.py"
    )
    foreach ($File in $RequiredFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $ProbeDir $File))) { throw "Missing bundled file: $File" }
    }
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $HelpOutput = (& "$ProbeDir\berry.exe" --help 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0 -or $HelpOutput -notmatch 'Usage') { throw "Bundled launcher failed: $HelpOutput" }
    & "$ProbeDir\runtime\git\cmd\git.exe" --version
    if ($LASTEXITCODE -ne 0) { throw "Bundled Git failed in system-only PATH." }
    & "$PSScriptRoot\test-standalone-python.ps1" -PythonDir "$ProbeDir\runtime\python" -BackendDir "$ProbeDir\backend"
    Write-Host "PASS: relocated zip contents, bundled launcher/Git, isolated backend imports and engine venv."
    Write-Host "Clean Windows VM startup, creation and exit remain a separate acceptance requirement."
} finally {
    $env:PATH = $SavedPath
    if (Test-Path -LiteralPath $ProbeDir) { Remove-Item -LiteralPath $ProbeDir -Recurse -Force }
}
