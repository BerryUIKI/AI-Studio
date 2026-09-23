# Berry AI Studio Launcher and Environment Manager

Date: 2026-09-23. Status: product scope approved; detailed design and implementation pending.

## Problem Observed in the Current Repository

The current Windows entry points are `scripts/launch.bat` and `scripts/start-berry.ps1`. They check for host Python, create `backend/.venv`, install Python dependencies on first run, open `http://127.0.0.1:8000`, and run Uvicorn in a terminal. The batch file opens the browser before server readiness. Both scripts assume a matching `frontend/dist` already exists; the backend serves that directory only if present. `frontend/dist` is ignored by Git. The scripts do not check frontend availability, handle an occupied port, or provide a unified view of Berry, ComfyUI, WebUI and cloud readiness.

The backend already has installation, engine connection and lifecycle services. A manager should orchestrate and present these existing capabilities, avoiding a second independent process/installation implementation.

The milestone report's automated tests and build are useful baseline evidence. They do not establish clean-machine onboarding or real multi-process lifecycle behavior; these require separate verification.

## Approved Product Shape

A Berry launcher starts before the main workspace and remains available as the unified environment manager. It opens the creative workspace, presents the model inventory, and manages installation, deployment, startup, shutdown, and updates for Berry-managed ComfyUI and Stable Diffusion WebUI. The main workspace stays focused on creation and may link back to manager views. External engine installations remain under user control.

Rust is the preferred implementation language for the launcher. The desktop UI framework and packaging format are engineering choices to validate. The launcher owns Berry's own application process. Existing backend engine supervisors and model catalog remain the authoritative services for engine operations and model data. A Rust UI should call those services through a versioned local interface rather than creating another installer, model database, or process supervisor. Bootstrap work required before the backend is available needs one documented ownership boundary.

The target newcomer flow is: start Berry from one Windows entry point, see readiness and recovery guidance, inspect local models, choose cloud-only or a local engine, and enter the canvas when Berry is ready. Local engines start only on explicit user action or a saved user preference.

## Approved Requirements

| ID | Behavior | Acceptance condition |
| --- | --- | --- |
| L01 | Single entry point | A user can open Berry on a clean supported Windows machine without running developer commands or prebuilding the frontend. Release packaging includes the frontend and a controlled backend runtime. |
| L02 | Accurate startup | Show startup stages and open the workspace only after a successful health/readiness probe. A missing frontend is a visible packaging error, not a blank page or API-only screen. |
| L03 | No duplicate processes | A second launch focuses or opens the existing workspace. The launcher checks ownership and health before reusing or stopping a process. An occupied non-Berry port yields an actionable choice. |
| L04 | Clear status | Show Berry core, managed ComfyUI, managed WebUI, external connections, cloud configuration, and model readiness separately. Distinguish installed, stopped, starting, ready, degraded, failed, and unavailable. |
| L05 | Controlled engines | Install, configure, start, stop and update managed engines independently with progress and errors. Never stop or update external engines; never require local engines for cloud-only mode. |
| L06 | Recovery | Failed installs, unavailable models, disconnected engines, invalid credentials, and backend failures explain the next action and offer safe retry where supported. Preserve diagnostic logs without exposing secrets. |
| L07 | Shutdown policy | Closing the creative window does not silently kill active tasks. Provide an explicit Exit Berry action that handles Berry-owned processes and active tasks predictably. Preserve external processes. Decide whether managed engines stop on exit as a documented setting. |
| L08 | Updates | Manage Berry app updates and ComfyUI/WebUI updates as separate operations. Show installed and available versions, download size when known, compatibility, progress, restart needs, and rollback/recovery guidance. Do not silently update external engines or download large files. Model updates are a separate future decision. |
| L09 | Portability | Put OS-specific launch/process behavior behind adapters; Windows is the first release target. Keep the core and cloud-only mode free of GPU/PyTorch requirements. |
| L10 | Model inventory | Show the unified local model list in the launcher, including location, type, known/unknown engine compatibility, missing dependencies and indexing status. Let users add/remove scan roots and rescan without deleting model files. Reuse the backend model catalog as the source of truth. |
| L11 | Rust launcher boundary | Implement the launcher in Rust or document a concrete technical blocker before changing this direction. Do not duplicate backend engine/model business logic; define a versioned local protocol, startup ownership and failure behavior. |
| L12 | Safe engine updates | Before updating a managed engine, check active jobs, stop/restart needs and compatibility. Preserve models, projects, credentials and user configuration. An interrupted or failed update must leave a recoverable recorded state. Do not claim rollback unless a restore path is implemented and tested. |

## Suggested First Implementation Slice

1. Validate the current batch and PowerShell scripts on a clean Windows environment, including frontend build artifacts, Python prerequisites, port collisions and relaunch. Record actual results.
2. Prototype a Rust launcher that boots Berry, checks readiness, and opens the workspace; document packaging and the local protocol.
3. Reuse backend engine manager, installer and model catalog through the local protocol. Add manager views for engine state, model inventory, install progress and recovery.
4. Design and implement separate Berry, ComfyUI and WebUI update flows with version pinning, preserved user data, and tested failure recovery.
5. Package the frontend and backend runtime into a user-facing Windows entry point.
6. Verify clean install, second launch, cloud-only launch, model inventory, managed/external engine lifecycle, interrupted install/update, active-task exit, and restart persistence on Windows.

## Implementation Status & Review Evidence (L01–L12)

The following architectural and implementation details document the verified status across all requirements:

### 1. L01: Clean-Machine Entry Point vs Developer Fallback
- **Distributed Release Path**: A clean Windows machine requires **zero host Python, zero Node.js, and zero build commands**. The release distribution bundles `berry.exe`, pre-compiled static assets in `frontend/dist/`, and an embedded, hermetic Python runtime at `runtime/python/python.exe`.
  - The launcher's `find_python_executable` checks:
    1. `runtime/python/python.exe` (Bundled hermetic runtime — 1st priority).
    2. `backend/.venv/Scripts/python.exe` (Pre-existing local venv — 2nd priority).
    3. Host system `python.exe` (Developer fallback only).
- **Developer Checkout Fallback**: Running from source via `scripts/launch.bat` or `scripts/start-berry.ps1` is strictly for developers working on the source repository. It bootstraps `backend/.venv` using host Python and warns if `frontend/dist` has not yet been built with `pnpm build`.

### 2. L02 & L03: Accurate Startup, Readiness Probe & Single-Instance Guarantee
- The Rust launcher performs a 4-stage readiness check: Environment inspection -> Subprocess spawn -> HTTP `/api/v1/health` and `/api/v1/manager/status` probe -> Browser launch.
- If `frontend/dist` is missing in development mode, visiting port 8000 renders an informative HTML diagnostic page rather than a blank 404 or API raw screen.
- A Win32 Named Mutex (`Global\BerryAIStudioLauncherMutex`) guarantees single-instance execution. Launching a second instance detects the mutex, leaves the existing process running, and focuses or navigates to the active workspace in the user's browser.
- Port collision checks distinguish between an existing healthy Berry instance (which is focused) and an alien process occupying the port (which outputs an actionable diagnostic message with `BERRY_PORT` override guidance).

### 3. L08: Application Updates vs Engine Updates (Installation & Limitations)
- **Engine Updates**: Managed independently via `/api/v1/runtime/{engine_type}/update` and `berry engine update <comfyui|webui>`.
- **Application Updates**: Checked via `/api/v1/updates/check` and triggered via `/api/v1/updates/app` or `berry update app`.
  - **Git Mode (Source Checkouts)**: Executes `git pull --ff-only` and reports the updated commit hash.
  - **Packaged Windows Mode**: Windows OS file locking prevents replacing the active running `berry.exe` and loaded DLLs in-place. The application update endpoint returns structured guidance with download URLs for the latest release package, noting that all user data (projects, credentials, custom model scan roots) in `%LOCALAPPDATA%\BerryAIStudio` is strictly preserved across updates.

### 4. L09 & L11: Rust Launcher Ownership & Cross-Platform Boundary
- **Platform Separation**:
  - **Windows-Specific Adapters**:
    - `launcher/src/single_instance.rs`: Windows Named Mutex (`CreateMutexW`, `GetLastError`).
    - `launcher/src/backend.rs`: Windows process creation flag `CREATE_NO_WINDOW (0x08000000)` and browser invocation via `cmd /c start`.
  - **Portable Components**:
    - `launcher/src/port.rs`: Standard library `TcpListener` for port readiness probing.
    - `launcher/src/client.rs`: Standard HTTP client (`ureq`) interfacing with backend REST API.
    - `launcher/src/update.rs`: Generic manifest and update orchestration.
- **Architectural Boundary**: The Rust launcher supervises the Berry backend process and serves as the CLI/desktop entry point. It delegates all model indexing, engine installation, lifecycle supervision, and task execution to the backend's local protocol (`/api/v1/manager/*`, `/api/v1/runtime/*`, `/api/v1/models/*`), preventing duplicate business logic.

### 5. L10: Unified Model Inventory Accessibility
- Users can inspect and manage model inventory from both the CLI and GUI:
  - **CLI**: `berry models list`, `berry models rescan`, `berry models roots`, `berry models add-root <path> <label>`, `berry models remove-root <root_id>`.
  - **GUI**: Header **"Environment"** modal -> **"Model Inventory"** tab, as well as a direct shortcut **"Models ↗"** in the creative canvas dock.
  - Shows file paths, model families (SDXL, SD 1.5, Flux, LoRA, Upscaler), engine compatibility tags (`ComfyUI`, `SD WebUI`), and missing dependencies (e.g., external CLIP or VAE requirements).
  - Adding or removing scan roots is non-destructive and never deletes weights from the filesystem.

### 6. L12: Safe Engine Updates & Rollback Truthfulness
- Before updating an engine, Berry verifies that no tasks are actively running (`active_tasks == 0`).
- **Rollback Scope**:
  - Before pulling changes, the supervisor captures the current git commit (`git rev-parse HEAD`).
  - If `git pull` or dependency installation fails, the engine is restored to the previous commit using `git checkout <previous_commit>`.
  - User weights in `models/`, outputs in `output/`, and user configuration files are explicitly preserved.
  - *Limitation Clarification*: Rollback restores the git commit and repository tree; it does not roll back pip wheel modifications inside the virtualenv if a package was overwritten. The system records `EngineUpdateStatus.ROLLED_BACK` with full diagnostic output.
