# Full, relocatable CPython with venv/ensurepip for optional engine environments.
param (
    [string]$TargetDir = "$PSScriptRoot\..\runtime\python-standalone",
    [string]$ArchivePath = ""
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$TargetDir = [IO.Path]::GetFullPath($TargetDir)
$AllowedRoot = Join-Path $RepoRoot "runtime"
$ReviewRoot = Join-Path $RepoRoot ".review-runtime"
if (-not ($TargetDir.StartsWith("$AllowedRoot\", [StringComparison]::OrdinalIgnoreCase) -or
          $TargetDir.StartsWith("$ReviewRoot\", [StringComparison]::OrdinalIgnoreCase))) {
    throw "Runtime target must be a child of repository runtime/ or .review-runtime/."
}
# Pin both source and checksum; an embeddable zip or host venv is not equivalent.
$RuntimeUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.12.14%2B20260901-x86_64-pc-windows-msvc-install_only.tar.gz"
$RuntimeSha256 = "e90c1b6419da3bd812dd73bb3de40287a21abf153438147639ec5e20375ea93f"
$StageDir = "$TargetDir.prepare-$([guid]::NewGuid().ToString('N'))"
$BackupDir = "$TargetDir.previous-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null
$SavedTemp = $env:TEMP
$SavedTmp = $env:TMP
$env:TEMP = New-Item -ItemType Directory -Path "$StageDir\temp" -Force | Select-Object -ExpandProperty FullName
$env:TMP = $env:TEMP
try {
    $Archive = Join-Path $StageDir "python.tar.gz"
    if ($ArchivePath) {
        Copy-Item -LiteralPath $ArchivePath -Destination $Archive
    } else {
        Write-Host "Downloading pinned CPython 3.12.14 runtime..."
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $RuntimeUrl -OutFile $Archive -UseBasicParsing -TimeoutSec 180
    }
    if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $RuntimeSha256) {
        throw "Python archive checksum mismatch; existing runtime was preserved."
    }
    & tar -xf $Archive -C $StageDir
    if ($LASTEXITCODE -ne 0) { throw "Python archive extraction failed." }
    $PreparedDir = Join-Path $StageDir "python"
    $PreparedPython = Join-Path $PreparedDir "python.exe"
    if (-not (Test-Path -LiteralPath $PreparedPython)) { throw "Archive is missing python/python.exe." }
    & $PreparedPython -I -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw "Runtime ensurepip failed." }
    & $PreparedPython -I -m pip install -r "$RepoRoot\backend\requirements.txt" --no-warn-script-location --no-cache-dir
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
    @{ source = $RuntimeUrl; sha256 = $RuntimeSha256; version = "3.12.14" } |
        ConvertTo-Json | Set-Content -LiteralPath "$PreparedDir\berry-runtime.json" -Encoding UTF8
    & "$PSScriptRoot\test-standalone-python.ps1" -PythonDir $PreparedDir
    # Promote only a validated runtime. Keep the old one until relocation also passes.
    if (Test-Path -LiteralPath $TargetDir) { Move-Item -LiteralPath $TargetDir -Destination $BackupDir }
    try {
        Move-Item -LiteralPath $PreparedDir -Destination $TargetDir
        & "$PSScriptRoot\test-standalone-python.ps1" -PythonDir $TargetDir
    } catch {
        if (Test-Path -LiteralPath $TargetDir) { Remove-Item -LiteralPath $TargetDir -Recurse -Force }
        if (Test-Path -LiteralPath $BackupDir) { Move-Item -LiteralPath $BackupDir -Destination $TargetDir }
        throw
    }
    if (Test-Path -LiteralPath $BackupDir) { Remove-Item -LiteralPath $BackupDir -Recurse -Force }
    Write-Host "Validated standalone runtime ready at $TargetDir"
} finally {
    $env:TEMP = $SavedTemp
    $env:TMP = $SavedTmp
    # Both paths were derived from the checked absolute repository target above.
    if (Test-Path -LiteralPath $StageDir) { Remove-Item -LiteralPath $StageDir -Recurse -Force }
}
