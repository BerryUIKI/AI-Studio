# Clean-Machine Testing Guide (L01 Acceptance)

This document describes the procedure for verifying that Berry AI Studio packages work on a clean Windows machine without Python, Git, or Node.js development tools installed.

## Purpose

Issue #118 requires that the Windows package be completely self-contained. The only way to verify this requirement is to test on an actual clean Windows VM or machine that has never had development tools installed.

## Test Environment Requirements

### Clean Windows VM Specifications
- **OS**: Windows 10 (version 21H2 or later) or Windows 11
- **Architecture**: 64-bit (x86_64)
- **RAM**: 4 GB minimum, 8 GB recommended
- **Disk**: 10 GB free space minimum
- **Network**: Internet connection for cloud API testing
- **Development Tools**: NONE - no Python, Git, Node.js, Visual Studio, or other dev tools

### Tools NOT Allowed on Test VM
- Python (any version)
- Git for Windows
- Node.js / npm / pnpm
- Visual Studio / Visual Studio Code
- MinGW / MSYS2 / Cygwin
- Anaconda / Miniconda
- Any other development runtime or compiler

### Tools Allowed on Test VM
- Modern web browser (Chrome, Edge, Firefox)
- 7-Zip or other archive extractor (for .zip extraction)
- Text editor (Notepad, Notepad++)
- Process monitor tools (optional, for diagnostics)

## Test Procedure

### Phase 1: Package Preparation (Host Machine)

On your development machine:

```powershell
# 1. Build the package
cd D:\dev\AI-Studio
git checkout dev
git pull origin dev

# 2. Run packaging script
.\scripts\package-windows-release.ps1 -Version "0.1.0"

# 3. Run automated smoke tests
.\scripts\smoke-test-package.ps1 -Version "0.1.0"

# 4. Run build order validation
.\scripts\test-build-order.ps1

# 5. Verify the package exists
dir dist\Berry-AI-Studio-v0.1.0-windows-x64.zip
```

Expected output:
- `dist/Berry-AI-Studio-v0.1.0-windows-x64.zip` created
- All smoke tests pass
- Build order validation passes

### Phase 2: Clean VM Setup

1. **Provision a fresh Windows VM** using:
   - Hyper-V (Windows Pro/Enterprise)
   - VirtualBox (free)
   - VMware Workstation/Player
   - Cloud VM (Azure, AWS, GCP)

2. **Verify VM is clean**:
   ```cmd
   python --version
   git --version
   node --version
   ```
   All commands should fail with "not recognized" errors.

3. **Transfer the package**:
   - Copy `Berry-AI-Studio-v0.1.0-windows-x64.zip` to the VM
   - Use shared folders, network transfer, or USB passthrough
   - Verify zip integrity (size and CRC if available)

### Phase 3: Installation Test

On the clean VM:

1. **Extract the package**:
   ```cmd
   cd C:\Users\<YourUser>\Downloads
   # Right-click Berry-AI-Studio-v0.1.0-windows-x64.zip → Extract All
   # Or use 7-Zip: "Extract Here"
   cd Berry-AI-Studio-v0.1.0-windows-x64
   dir
   ```

   Expected files:
   - `berry.exe`
   - `Berry AI Studio.exe`
   - `Berry.bat`
   - `README.txt`
   - `frontend/` directory with `dist/index.html`
   - `backend/` directory with `app/main.py`
   - `runtime/python/` directory with `python.exe`
   - `runtime/git/` directory with `cmd/git.exe`

2. **Verify bundled Python works**:
   ```cmd
   runtime\python\python.exe --version
   runtime\python\python.exe -c "import fastapi; print('OK')"
   ```

   Expected output:
   - Python version (e.g., `Python 3.11.9`)
   - `OK` from the import test

3. **Verify bundled Git works**:
   ```cmd
   runtime\git\cmd\git.exe --version
   ```

   Expected output:
   - Git version (e.g., `git version 2.47.1.windows.1`)

### Phase 4: Startup Test

1. **Launch Berry**:
   ```cmd
   Berry.bat
   ```
   OR double-click `berry.exe` from Windows Explorer.

2. **Verify startup sequence**:
   - Console shows: "Berry AI Studio (Windows Launcher)"
   - Stage 1: Validating runtime environment
   - Stage 2: Checking ports and locks
   - Stage 3: Spawning Berry core (127.0.0.1:8000)
   - Stage 4: Probing service readiness
   - Console shows: "Core service is READY"
   - Browser opens automatically to `http://127.0.0.1:8000`

3. **Expected behaviors**:
   - ✅ Berry launches without errors
   - ✅ No Python installation prompts
   - ✅ No missing DLL errors
   - ✅ Web interface loads in browser
   - ✅ Console shows readiness message

4. **Common failures and diagnostics**:
   - "Python not found": Package missing bundled Python runtime
   - "Module not found: fastapi": Bundled Python missing dependencies
   - "Backend failed to become ready": Check console for Python errors
   - Browser doesn't open: Manually navigate to `http://127.0.0.1:8000`

### Phase 5: Cloud Onboarding Test

Test cloud-only operation (no local GPU required):

1. **Configure cloud provider**:
   - Click "Cloud BYOK" in the top navigation
   - Select provider (e.g., OpenAI, Fal.ai, SiliconFlow)
   - Enter a valid API key (use a test key with minimal balance)
   - Click "Test Connection"

2. **Expected behaviors**:
   - ✅ Connection test succeeds
   - ✅ API key is stored securely (not visible in UI after save)
   - ✅ Provider capabilities are shown

3. **Generate a test image** (optional, requires API credits):
   - Enter a simple prompt: "a red apple"
   - Click "Generate"
   - Verify task starts and shows progress
   - Verify result appears on canvas

### Phase 6: Engine Installation Prerequisites Test

Test that engine installation can be initiated without system Git:

1. **Open Environment Manager**:
   - Click "Environment" in the navigation
   - Click "Install ComfyUI" or "Install WebUI"

2. **Verify installation starts**:
   - Installation dialog shows progress
   - No "Git not found" errors appear
   - Installation uses bundled Git from `runtime/git/`

3. **Note**: Full engine installation requires ~10-20 minutes and several GB of downloads. For clean-VM acceptance, verifying that installation *starts* without Git errors is sufficient. Full installation testing is covered by engine-specific tests.

### Phase 7: Safe Exit Test

1. **Exit Berry**:
   - In the web UI, click "Exit Berry" if available
   - OR press Ctrl+C in the console window
   - OR close the console window

2. **Expected behaviors**:
   - ✅ Backend process terminates cleanly
   - ✅ No orphaned Python or Berry processes remain
   - ✅ Console shows "Berry AI Studio process ended"

3. **Verify cleanup**:
   ```cmd
   tasklist | findstr python
   tasklist | findstr berry
   ```
   
   Expected: No Berry or Python processes running.

## Acceptance Criteria Checklist

Mark each criterion as tested on a clean VM:

- [ ] Package extracts without errors
- [ ] `runtime/python/python.exe` executes and has all dependencies
- [ ] `runtime/git/cmd/git.exe` executes successfully
- [ ] `berry.exe --help` works without system Python
- [ ] Berry launches and reaches "READY" state
- [ ] Web interface loads at `http://127.0.0.1:8000`
- [ ] Cloud provider configuration works
- [ ] Engine installation can be initiated without system Git
- [ ] Berry exits cleanly without orphaned processes
- [ ] No developer-machine paths appear in error messages

## Test Evidence

Document the following for issue #118 completion:

1. **VM Environment**:
   - Windows version: `winver` output
   - Screenshot of `python --version` failing (before Berry)
   - Screenshot of `git --version` failing (before Berry)

2. **Package Verification**:
   - Package file size
   - Screenshot of extracted directory structure
   - Output of bundled Python version check

3. **Startup Evidence**:
   - Full console output from Berry launch
   - Screenshot of browser showing Berry UI
   - Screenshot of "Core service is READY" message

4. **Test Results**:
   - Date and time of testing
   - Tester name or identifier
   - Pass/fail status for each acceptance criterion
   - Any issues encountered and their resolution

## Reporting Results

When reporting clean-VM test results in issue #118:

```markdown
## Clean-VM Test Results

**Environment:**
- Windows Version: Windows 11 Pro 23H2 (Build 22631.4602)
- VM Platform: Hyper-V / VirtualBox / VMware
- Test Date: 2026-01-XX
- Package Version: v0.1.0

**Test Status:** PASS / FAIL / PARTIAL

**Acceptance Criteria:**
- ✅ Package extracts without errors
- ✅ Bundled Python executes independently
- ✅ Bundled Git executes successfully
- ✅ Berry launches without system dependencies
- ✅ Web interface loads successfully
- ✅ Cloud onboarding works
- ✅ Engine installation prerequisites met
- ✅ Clean exit without orphaned processes

**Issues Found:**
- None / [List specific issues]

**Evidence:**
- [Attach screenshots or link to test log]
```

## Automated Host-Machine Tests vs. Clean-VM Tests

**Important distinction:**

- **Host-machine tests** (`smoke-test-package.ps1`): Run on the development machine with PATH sanitization. These can verify package structure and that the bundled runtime *can* work, but cannot prove it works on a truly clean machine.

- **Clean-VM tests** (this document): Run on a VM without any development tools. These are the ONLY way to verify L01 acceptance (zero host dependencies).

Both are required:
1. Host-machine smoke tests run on every build (automated)
2. Clean-VM tests run before release (manual verification)

## Troubleshooting

### Issue: "The system cannot execute the specified program"
- **Cause**: Bundled Python missing required DLLs
- **Fix**: Ensure `runtime/python/` includes all DLLs from embeddable package

### Issue: "Module not found" errors in console
- **Cause**: Bundled Python missing dependencies
- **Fix**: Run `prepare-standalone-python.ps1` again and verify requirements installation

### Issue: Browser doesn't open automatically
- **Not a failure**: Manually navigate to `http://127.0.0.1:8000`
- Berry is still considered functional if the web UI is accessible

### Issue: "Git not found" during engine installation
- **Cause**: Portable Git not bundled or PATH incorrect
- **Fix**: Verify `runtime/git/cmd/git.exe` exists in package

### Issue: Engine installation fails immediately
- **Cause**: Git bundle incomplete or corrupted
- **Test**: Run `runtime\git\cmd\git.exe --version` to verify Git works
