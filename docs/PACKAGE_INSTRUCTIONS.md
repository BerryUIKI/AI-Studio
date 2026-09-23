# Berry AI Studio: Windows Packaging & Clean-Machine Distribution Guide

Date: **2026-09-23**  
Milestone Requirement: **L01 (Single Entry Point & Zero Host Prerequisites)**

---

## 1. Overview

Berry AI Studio provides an automated, self-contained Windows portable release package. A new Windows user can download the release archive, extract it, and immediately run the creative studio without installing:
- **Zero Host Python required** (a controlled runtime is bundled in `runtime/python/`).
- **Zero Node.js / pnpm required** (production static assets are pre-compiled in `frontend/dist/`).
- **Zero Git or compilation required** (the native Rust launcher is pre-built as `berry.exe`).

---

## 2. Package Structure

When built, the portable release directory `dist/Berry-AI-Studio-v0.1.0-windows-x64/` has the following layout:

```text
Berry-AI-Studio-v0.1.0-windows-x64/
├── berry.exe                # Native Windows Rust launcher & environment manager
├── Berry.bat                # Convenient double-click launcher wrapper
├── README.txt               # Quickstart guide & support links
├── runtime/
│   └── python/              # Isolated, hermetic Python runtime with dependencies pre-installed
│       ├── python.exe
│       ├── Lib/site-packages/
│       └── Scripts/
├── backend/                 # Backend application services (FastAPI, schemas, runners, storage)
│   ├── app/
│   ├── requirements.txt
│   └── ...
└── frontend/
    └── dist/                # Pre-compiled static web SPA (Vite + React)
        ├── index.html
        └── assets/
```

---

## 3. How to Build the Package

From the repository root, run the packaging script using PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-windows-release.ps1
```

### Build Stages Executed:
1. **`[1/5] Building native Rust launcher`**: Compiles `launcher/target/release/berry.exe` with optimizations.
2. **`[2/5] Building frontend bundle`**: Runs `pnpm build` to compile the Vite React application into `frontend/dist/`.
3. **`[3/5] Staging directory`**: Creates a clean directory at `dist/Berry-AI-Studio-v<version>-windows-x64/`.
4. **`[4/5] Populating components`**: Copies the launcher, frontend assets, backend services, and bundles the isolated Python runtime. Generates `Berry.bat` and `README.txt`.
5. **`[5/5] Compressing archive`**: Compresses the staged directory into a `.zip` archive ready for distribution.

---

## 4. How to Verify the Package (Automated Smoke Test)

Run the automated smoke test script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\smoke-test-package.ps1
```

### Checks Performed:
- **Check 1**: Validates existence of directory and `.zip` archive.
- **Check 2**: Validates all essential files (`berry.exe`, `Berry.bat`, `README.txt`, `runtime/python/python.exe`, `frontend/dist/index.html`).
- **Check 3**: Invokes `berry.exe --help` in an isolated environment with a **sanitized PATH** (stripping out any host Python, Node.js, and Git), verifying that the launcher runs cleanly with exit code 0.
- **Check 4**: Validates that the bundled Python runtime executes and imports core dependencies (`fastapi`, `pydantic`) without referencing host libraries.

---

## 5. End-User Launch Instructions

1. Extract `Berry-AI-Studio-v0.1.0-windows-x64.zip` to any folder (e.g. `C:\BerryAIStudio`).
2. Double-click `Berry.bat` or `berry.exe`.
3. Berry will execute 4-stage readiness checks and open `http://127.0.0.1:8000` in the default browser.
4. All user data (projects, assets, credentials) is saved to `%LOCALAPPDATA%\BerryAIStudio` and `%LOCALAPPDATA%\AI-Workflow`, keeping the application folder clean and portable.
