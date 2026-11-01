param (
    [string]$PythonDir = "$PSScriptRoot\..\runtime\python-standalone",
    [string]$BackendDir = "$PSScriptRoot\..\backend"
)
$ErrorActionPreference = "Stop"
$PythonDir = (Resolve-Path -LiteralPath $PythonDir).Path
$PythonExe = Join-Path $PythonDir "python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) { throw "Missing standalone python.exe: $PythonExe" }
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$ProbeDir = Join-Path $RepoRoot ".review-runtime\runtime-probe-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $ProbeDir -Force | Out-Null
$SavedPath = $env:PATH
$SavedHome = $env:PYTHONHOME
$SavedPythonPath = $env:PYTHONPATH
$SavedData = $env:BERRY_DATA_DIR
$SavedTemp = $env:TEMP
$SavedTmp = $env:TMP
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:PYTHONHOME = $null
    $env:PYTHONPATH = $null
    $env:BERRY_DATA_DIR = Join-Path $ProbeDir "data"
    $env:TEMP = New-Item -ItemType Directory -Path "$ProbeDir\temp" -Force | Select-Object -ExpandProperty FullName
    $env:TMP = $env:TEMP
    & $PythonExe -I "$PSScriptRoot\verify_runtime.py" --runtime $PythonDir --backend $BackendDir --work-dir $ProbeDir
    if ($LASTEXITCODE -ne 0) { throw "Standalone runtime verification failed." }
} finally {
    $env:PATH = $SavedPath
    $env:PYTHONHOME = $SavedHome
    $env:PYTHONPATH = $SavedPythonPath
    $env:BERRY_DATA_DIR = $SavedData
    $env:TEMP = $SavedTemp
    $env:TMP = $SavedTmp
    # ProbeDir is an absolute child of repository .review-runtime/.
    Remove-Item -LiteralPath $ProbeDir -Recurse -Force
}
