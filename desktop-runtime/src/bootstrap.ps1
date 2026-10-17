# Embedded Windows core-runtime installer. All writes stay in designated app data.
param([string]$SourceRoot, [string]$DataRoot, [string]$RuntimeDir)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$DataRoot = [IO.Path]::GetFullPath($DataRoot)
$RuntimeDir = [IO.Path]::GetFullPath($RuntimeDir)
function Assert-Owned([string]$Path) {
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith("$DataRoot\runtime\core\", [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Setup path is outside application runtime storage.'
    }
    $cursor = $resolved
    while ($cursor -and $cursor.Length -ge $DataRoot.Length) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Setup paths must not redirect through junctions or symbolic links.'
        }
        $cursor = Split-Path -Parent $cursor
    }
}
function Progress([string]$Stage) { Write-Output (@{stage=$Stage} | ConvertTo-Json -Compress) }
Assert-Owned $RuntimeDir
if (-not (Test-Path -LiteralPath "$SourceRoot\backend\requirements.txt")) { throw 'Application dependency manifest is missing.' }
$Stage = Join-Path $RuntimeDir ('.setup-' + [guid]::NewGuid().ToString('N'))
$Target = Join-Path $RuntimeDir 'python'
$Backup = Join-Path $RuntimeDir ('.previous-' + [guid]::NewGuid().ToString('N'))
Assert-Owned $Stage
New-Item -ItemType Directory -Path $Stage -Force | Out-Null
$Log = Join-Path $Stage 'installation.log'
$SavedTemp = $env:TEMP
$SavedTmp = $env:TMP
$env:TEMP = New-Item -ItemType Directory -Path "$Stage\temp" -Force | Select-Object -ExpandProperty FullName
$env:TMP = $env:TEMP
$env:PYTHONHOME = $null
$env:PYTHONPATH = $null
$env:PIP_CONFIG_FILE = 'NUL'
try {
    Progress 'downloading'
    $Archive = Join-Path $Stage 'python.tar.gz'
    $RuntimeUrl = 'https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.12.14%2B20260901-x86_64-pc-windows-msvc-install_only.tar.gz'
    $RuntimeSha256 = 'e90c1b6419da3bd812dd73bb3de40287a21abf153438147639ec5e20375ea93f'
    Invoke-WebRequest -Uri $RuntimeUrl -OutFile $Archive -UseBasicParsing -TimeoutSec 180
    Progress 'verifying'
    if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $RuntimeSha256) { throw 'Python download checksum mismatch.' }
    & "$env:SystemRoot\System32\tar.exe" -xf $Archive -C $Stage
    if ($LASTEXITCODE -ne 0) { throw 'Python extraction failed.' }
    $Python = Join-Path $Stage 'python\python.exe'
    if (-not (Test-Path -LiteralPath $Python)) { throw 'Downloaded runtime is incomplete.' }
    $Requirements = Join-Path $Stage 'requirements.txt'
    Copy-Item -LiteralPath "$SourceRoot\backend\requirements.txt" -Destination $Requirements
    Progress 'installing'
    & $Python -I -m ensurepip --upgrade *> $Log
    if ($LASTEXITCODE -ne 0) { throw 'Package tooling setup failed.' }
    & $Python -I -m pip --isolated install --disable-pip-version-check --no-input --no-user --only-binary=:all: --index-url https://pypi.org/simple --timeout 30 --retries 2 --no-cache-dir --prefix "$Stage\python" -r $Requirements *>> $Log
    if ($LASTEXITCODE -ne 0) { throw 'Application dependency installation failed.' }
    Progress 'validating'
    $Probe = 'import sys,pathlib; assert sys.version_info >= (3,10); assert pathlib.Path(sys.prefix).resolve()==pathlib.Path(sys.executable).resolve().parent; import uvicorn,fastapi,pydantic,httpx,aiosqlite,PIL,multipart,quickjs; assert "torch" not in sys.modules'
    & $Python -I -c $Probe *>> $Log
    if ($LASTEXITCODE -ne 0) { throw 'Core environment validation failed.' }
    $Ready = @{ requirements_sha256=(Get-FileHash -LiteralPath $Requirements -Algorithm SHA256).Hash.ToLowerInvariant(); python_version='3.12.14'; archive_sha256=$RuntimeSha256 }
    [IO.File]::WriteAllText("$Stage\python\berry-core-ready.json", ($Ready | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
    Assert-Owned $Target
    Assert-Owned $Backup
    if (Test-Path -LiteralPath $Target) { Move-Item -LiteralPath $Target -Destination $Backup }
    try {
        Move-Item -LiteralPath "$Stage\python" -Destination $Target
        & "$Target\python.exe" -I -c $Probe *>> $Log
        if ($LASTEXITCODE -ne 0) { throw 'Core environment relocation failed.' }
    } catch {
        # Retain failed and previous installations for diagnosis; never overwrite user data.
        if (Test-Path -LiteralPath $Target) {
            $Failed = Join-Path $RuntimeDir ('.failed-' + [guid]::NewGuid().ToString('N'))
            Assert-Owned $Failed
            Move-Item -LiteralPath $Target -Destination $Failed
        }
        if (Test-Path -LiteralPath $Backup) { Move-Item -LiteralPath $Backup -Destination $Target }
        throw
    }
    Copy-Item -LiteralPath $Log -Destination "$RuntimeDir\last-installation.log" -Force
    Progress 'complete'
} catch {
    # Fixed error text prevents package/index/environment secrets from reaching UI/log output.
    Progress 'failed'
    exit 1
} finally {
    if (Test-Path -LiteralPath $Log) { Copy-Item -LiteralPath $Log -Destination "$RuntimeDir\last-installation.log" -Force }
    $env:TEMP = $SavedTemp
    $env:TMP = $SavedTmp
    # The unique staging path is verified again before recursive cleanup.
    Assert-Owned $Stage
    if (Test-Path -LiteralPath $Stage) { Remove-Item -LiteralPath $Stage -Recurse -Force }
}
