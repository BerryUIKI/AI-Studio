# Quick Test Reference for Issue #118

## Automated Tests (Development Machine)

Run these commands in PowerShell from the repository root:

### Step 1: Prepare Standalone Python Runtime
```powershell
# Clean any previous runtime
Remove-Item -Recurse -Force runtime/python-standalone -ErrorAction SilentlyContinue

# Download and configure Python 3.11.9 embeddable package
# Downloads ~80 MB, takes 5-10 minutes
.\scripts\prepare-standalone-python.ps1
```

**Expected output**:
- Downloads Python embeddable package
- Installs pip
- Installs all backend dependencies
- Reports "Standalone Python Runtime Ready!"

### Step 2: Verify Standalone Python
```powershell
.\scripts\test-standalone-python.ps1
```

**Expected output**:
- All 5 tests pass
- Python version shown (3.11.9)
- All backend packages verified

### Step 3: Build Package
```powershell
# Build complete package (~5-10 minutes)
.\scripts\package-windows-release.ps1 -Version "0.1.0"
```

**Expected output**:
- [0/6] Standalone Python verified
- [1/6] Frontend built (index.html + assets)
- [2/6] Tauri native app built
- [3/6] Rust launcher built
- [4/6] Staging complete
- [5/6] All components copied
- [6/6] Validation passed
- Package compressed to `dist/Berry-AI-Studio-v0.1.0-windows-x64.zip`

### Step 4: Verify Package
```powershell
.\scripts\smoke-test-package.ps1 -Version "0.1.0"
```

**Expected output**:
- [1/6] Artifacts exist
- [2/6] Essential files found
- [3/6] No developer paths detected
- [4/6] berry.exe works in clean PATH
- [5/6] Bundled Python executes
- [6/6] Portable Git bundled
- "All Package Smoke Tests PASSED!"

### Step 5: Validate Build Order
```powershell
.\scripts\test-build-order.ps1
```

**Expected output**:
- Frontend builds before Tauri ✓
- Package script has validation ✓
- Build Order Validation PASSED!

## Expected Package Size

- `dist/Berry-AI-Studio-v0.1.0-windows-x64.zip`: ~200-300 MB
- Extracted directory: ~400-500 MB

## Common Issues

### "pnpm: command not found"
```powershell
npm install -g pnpm
```

### "cargo: command not found"
Install Rust: https://rustup.rs/

### "Python download failed"
Check internet connection. Script downloads from python.org.

### "Tauri build failed"
Ensure frontend built first:
```powershell
cd frontend
pnpm install
pnpm build
cd ..
```

## Clean-VM Testing (Manual)

After automated tests pass, follow `docs/CLEAN_MACHINE_TESTING.md` for clean-VM verification.

## Quick Status Check

```powershell
# Check if all test scripts exist
dir scripts\*.ps1

# Check package exists
dir dist\Berry-AI-Studio-v0.1.0-windows-x64.zip

# Check standalone Python exists
dir runtime\python-standalone\python.exe
```
