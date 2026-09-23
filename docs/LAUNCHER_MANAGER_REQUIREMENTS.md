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

L01–L12 supplement the approved PRD. Exact update sources, release channels, version pins, packaging technology and rollback mechanism are engineering decisions that require evidence before implementation claims.

## Copyable Follow-Up Prompt for a Coding Agent

Implement the approved launcher/manager scope in `docs/LAUNCHER_MANAGER_REQUIREMENTS.md` (L01–L12). Read `docs/PRODUCT_VISION.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `AGENTS.md` first. Use Rust for the launcher unless a concrete blocker is documented. It must open Berry, show the shared model inventory, and manage installation/deployment, lifecycle and updates of Berry-managed ComfyUI and Stable Diffusion WebUI. Reuse backend engine and model services through a versioned local interface; avoid duplicate installers or databases. Start by auditing the current scripts and real clean-machine behavior. Implement in reviewable stages, recording packaging, process ownership, update recovery and cloud-only evidence. Preserve external engines and user data. Do not claim completion based only on unit tests or a frontend build. All repository artifacts and commits must be in English.
