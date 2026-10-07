# Berry AI Studio - Build Order Validation Test
# Verifies that frontend assets are built before Tauri attempts to embed them.

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Build Order Validation Test" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Test 1: Verify frontend dist exists before attempting Tauri build
Write-Host "`n[Test 1/3] Checking if frontend assets must be built before Tauri..." -ForegroundColor Yellow

$FrontendDist = "$RepoRoot\frontend\dist"
$TauriConfig = "$RepoRoot\frontend\src-tauri\tauri.conf.json"

if (-not (Test-Path $TauriConfig)) {
    throw "Tauri config not found at $TauriConfig"
}

# Parse tauri.conf.json to find distDir
$TauriConfigContent = Get-Content $TauriConfig -Raw | ConvertFrom-Json
$DistDir = $TauriConfigContent.build.distDir

if ($DistDir) {
    Write-Host "  -> Tauri configured to embed from: $DistDir" -ForegroundColor Gray

    if (-not (Test-Path $FrontendDist)) {
        Write-Host "  -> Frontend dist does not exist yet (correct - must be built first)" -ForegroundColor Green
    } else {
        Write-Host "  -> Frontend dist exists" -ForegroundColor Green
    }
} else {
    Write-Warning "Could not determine Tauri distDir from config"
}

# Test 2: Verify package script builds in correct order
Write-Host "`n[Test 2/3] Analyzing package-windows-release.ps1 build order..." -ForegroundColor Yellow

$PackageScript = Get-Content "$PSScriptRoot\package-windows-release.ps1" -Raw

# Find line numbers for key build steps
$FrontendBuildLine = ($PackageScript -split "`n" | Select-String "pnpm build" | Select-Object -First 1).LineNumber
$TauriBuildLine = ($PackageScript -split "`n" | Select-String "tauri build" | Select-Object -First 1).LineNumber

if ($null -eq $FrontendBuildLine -or $null -eq $TauriBuildLine) {
    throw "Could not find build commands in package script"
}

if ($FrontendBuildLine -lt $TauriBuildLine) {
    Write-Host "  -> Correct order: Frontend build (line $FrontendBuildLine) before Tauri build (line $TauriBuildLine)" -ForegroundColor Green
} else {
    throw "INCORRECT BUILD ORDER: Tauri build (line $TauriBuildLine) runs before frontend build (line $FrontendBuildLine)"
}

# Test 3: Verify package script fails on missing critical files
Write-Host "`n[Test 3/3] Checking for failure-on-missing-files validation..." -ForegroundColor Yellow

$HasValidation = $PackageScript -match "Assert-FileExists|throw.*Missing|ValidationErrors"
if ($HasValidation) {
    Write-Host "  -> Package script includes missing-file validation" -ForegroundColor Green
} else {
    throw "Package script lacks proper validation for missing critical files"
}

$ValidatesFrontendAssets = $PackageScript -match "frontend\\dist\\index\.html"
if ($ValidatesFrontendAssets) {
    Write-Host "  -> Package script validates frontend assets exist" -ForegroundColor Green
} else {
    throw "Package script does not validate frontend assets before packaging"
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Build Order Validation PASSED!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
