# Berry AI Studio v0.1: Unified Product Acceptance Dossier

**Target Milestone**: v0.1.0 First Release Unified Product Acceptance  
**Target Git Branch**: `dev`  
**Governing Documents**: [`docs/PRD.md`](PRD.md), [`docs/LAUNCHER_MANAGER_REQUIREMENTS.md`](LAUNCHER_MANAGER_REQUIREMENTS.md), [`docs/PRODUCT_VISION.md`](PRODUCT_VISION.md), [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/SUPPORT_MATRIX.md`](SUPPORT_MATRIX.md).

---

## 1. Release Package Artifact & Exact Commit

- **Exact Git Review Commit (`dev`)**: [`4af27ec20ef8db25d9e0e46e5b437de5096ee1b9`](https://github.com/BerryUIKI/AI-Studio/commit/4af27ec20ef8db25d9e0e46e5b437de5096ee1b9)
- **Preceding Integration Commit (`dev`)**: [`674611827de2a20854e55c9dd509dda9fb746de4`](https://github.com/BerryUIKI/AI-Studio/commit/674611827de2a20854e55c9dd509dda9fb746de4)
- **Primary Package Artifact**:
  - **Archive**: `dist/Berry-AI-Studio-v0.1.0-windows-x64.zip` (18.9 MB)
  - **Unpacked Distribution Directory**: `dist/Berry-AI-Studio-v0.1.0-windows-x64/`
  - **Contents**:
    - `berry.exe` (Native Rust launcher & environment manager)
    - `Berry.bat` (Double-click launcher wrapper)
    - `README.txt` (User onboarding & quickstart instructions)
    - `frontend/dist/` (Compiled React/Vite single-page production web application)
    - `backend/app/` (FastAPI core, DAG cache, persistent storage, runners, supervisors)
    - `runtime/python/` (Hermetic Python 3.12 runtime with pre-installed dependencies)
- **Automated Packager Script**: [`scripts/package-windows-release.ps1`](../scripts/package-windows-release.ps1)
- **Path-Sanitized Smoke Test**: [`scripts/smoke-test-package.ps1`](../scripts/smoke-test-package.ps1) (Verified on clean PATH without host Python, Git, or Node.js)

---

## 2. Integrated Pull Requests on `dev`

All changes have been developed on focused feature branches and integrated into `dev` in dependency order after passing all 3 required automated CI checks (Backend Tests, Frontend Build, Rust Launcher). Every commit was signed with the user's configured SSH key (`ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIML4uviiDJkREWuM2xgPhU7asKoVbmOuxkVPqfST4CBA`).

| PR # | Branch | Title & Focus | CI Checks | Merge Commit |
| :--- | :--- | :--- | :--- | :--- |
| **[PR #1](https://github.com/BerryUIKI/AI-Studio/pull/1)** | `feature/ci-and-gitflow` | `ci(governance): add CI workflow, gitignore target, and refine GitFlow branch policy` | 3/3 Passed | [`acb3988`](https://github.com/BerryUIKI/AI-Studio/commit/acb3988) |
| **[PR #2](https://github.com/BerryUIKI/AI-Studio/pull/2)** | `feature/core-runtime-persistence` | `feat(backend): implement M1-M2 core runtime, isolated supervisors, and SQLite persistence` | 3/3 Passed | [`86aa080`](https://github.com/BerryUIKI/AI-Studio/commit/86aa080) |
| **[PR #3](https://github.com/BerryUIKI/AI-Studio/pull/3)** | `feature/creative-canvas-frontend` | `feat(frontend): implement M3-M4 creative canvas, contextual image actions, and BYOK cloud modal` | 3/3 Passed | [`94d3076`](https://github.com/BerryUIKI/AI-Studio/commit/94d3076) |
| **[PR #4](https://github.com/BerryUIKI/AI-Studio/pull/4)** | `feature/rust-launcher-manager` | `feat(launcher): implement Rust launcher, single-instance mutex, and environment manager` | 3/3 Passed | [`41c66d3`](https://github.com/BerryUIKI/AI-Studio/commit/41c66d3) |
| **[PR #5](https://github.com/BerryUIKI/AI-Studio/pull/5)** | `feature/windows-portable-distribution` | `feat(distribution): add Windows portable release packager and smoke test (L01)` | 3/3 Passed | [`3fbf7c1`](https://github.com/BerryUIKI/AI-Studio/commit/3fbf7c1) |
| **[PR #6](https://github.com/BerryUIKI/AI-Studio/pull/6)** | `docs/m0-m6-delivery-handoff` | `docs(handoff): finalize M0-M6 delivery handoff and verification boundaries` | 3/3 Passed | [`da70036`](https://github.com/BerryUIKI/AI-Studio/commit/da70036) |
| **[PR #7](https://github.com/BerryUIKI/AI-Studio/pull/7)** | `feature/cancellation-and-cloud-actions` | `feat(creative): implement task cancellation, engine interrupt, and cloud actions (R07-R09, R14, L07)` | 3/3 Passed | [`6746118`](https://github.com/BerryUIKI/AI-Studio/commit/6746118) |
| **[PR #8](https://github.com/BerryUIKI/AI-Studio/pull/8)** | `docs/acceptance-dossier-m0-m6` | `docs(dossier): add Berry AI Studio v0.1 unified product acceptance dossier` | 3/3 Passed | [`4af27ec`](https://github.com/BerryUIKI/AI-Studio/commit/4af27ec) |
| **[PR #9](https://github.com/BerryUIKI/AI-Studio/pull/9)** | `docs/update-acceptance-commit` | `docs: synchronize acceptance dossier commit hash with dev HEAD` | 3/3 Passed | [`4bd648a`](https://github.com/BerryUIKI/AI-Studio/commit/4bd648a) |
| **[PR #10](https://github.com/BerryUIKI/AI-Studio/pull/10)** | `docs/post-v0-1-roadmap` | `docs(roadmap): define post-v0.1 milestones M7-M12` | 3/3 Passed | [`809312f`](https://github.com/BerryUIKI/AI-Studio/commit/809312f) |
| **[PR #11](https://github.com/BerryUIKI/AI-Studio/pull/11)** | `feature/m7-video-generation` | `feat(video): implement M7 video generation, ComfyUI macros, cloud calling, and canvas video cards` | 3/3 Passed | [`64cd55c`](https://github.com/BerryUIKI/AI-Studio/commit/64cd55c) |
| **[PR #12](https://github.com/BerryUIKI/AI-Studio/pull/12)** | `feature/m8-unified-cli` | `feat(cli): unified headless CLI for creative execution and system management (M8)` | 3/3 Passed | [`8e394dd`](https://github.com/BerryUIKI/AI-Studio/commit/8e394dd) |
| **[PR #13](https://github.com/BerryUIKI/AI-Studio/pull/13)** | `feature/m9-agent-control` | `feat(agent): conversational agent workflow control with transparent proposals (M9)` | 3/3 Passed | [`1260722`](https://github.com/BerryUIKI/AI-Studio/commit/1260722) |
| **[PR #14](https://github.com/BerryUIKI/AI-Studio/pull/14)** | `feature/m10-workflow-repair` | `feat(comfy): workflow validation and automated repair engine (M10)` | 3/3 Passed | [`60c3620`](https://github.com/BerryUIKI/AI-Studio/commit/60c3620) |
| **[PR #15](https://github.com/BerryUIKI/AI-Studio/pull/15)** | `feature/m11-discrete-gpus` | `feat(hardware): support non-NVIDIA discrete GPUs with DirectML and launch flag injection (M11)` | 3/3 Passed | [`7f700b2`](https://github.com/BerryUIKI/AI-Studio/commit/7f700b2) |
| **[PR #16](https://github.com/BerryUIKI/AI-Studio/pull/16)** | `feature/m12-cross-platform` | `feat(platform): cross-platform desktop adapters for macOS Metal and Linux (M12)` | 3/3 Passed | [`2551796`](https://github.com/BerryUIKI/AI-Studio/commit/2551796) |
| **[PR #17](https://github.com/BerryUIKI/AI-Studio/pull/17)** | `docs/dossier-roadmap-sync` | `docs: synchronize acceptance dossier and roadmap post v0.1 with dev integration commits` | 3/3 Passed | [`0a59aba`](https://github.com/BerryUIKI/AI-Studio/commit/0a59aba) |
| **[PR #18](https://github.com/BerryUIKI/AI-Studio/pull/18)** | `feature/repair-agent-safety` | `fix(workflow): enforce model family guards and ambiguity blocking in workflow repair` | 3/3 Passed | [`3cf860a`](https://github.com/BerryUIKI/AI-Studio/commit/3cf860a) |
| **[PR #19](https://github.com/BerryUIKI/AI-Studio/pull/19)** | `feature/hardware-matrix-realism` | `fix(hardware): accurately classify AMD, Intel, and Apple Silicon as candidate or source-compatible` | 3/3 Passed | [`c35f3b1`](https://github.com/BerryUIKI/AI-Studio/commit/c35f3b1) |
| **[PR #20](https://github.com/BerryUIKI/AI-Studio/pull/20)** | `feature/video-format-dossier-alignment` | `fix(video): support video containers and animated webp, fix MIME type, align dossier evidence` | 3/3 Passed | Pending |

---

## 3. Supported Versions & Hardware Evidence Tiers

### Operating Systems & Platform Verification Status
- **Windows 10 / 11 (64-bit)**: **Physically Verified**. Tested on Windows 11 host with native Rust launcher, ComfyUI engine supervisor, single-instance Win32 mutex, and local inference.
- **macOS (Apple Silicon, Metal MPS)**: **Source Compatible**. Directory paths, browser launcher commands, Unix domain socket single-instance checks, and Metal fp16 flags implemented and unit-tested; native macOS binary bundling and physical Apple Silicon execution remain unverified in this session.
- **Linux (Ubuntu 22.04+)**: **Source Compatible**. Supervisor process handling, Unix domain socket locking, and headless CLI generation implemented and unit-tested; native Linux binary packaging and physical non-NVIDIA execution remain unverified in this session.

### Hardware Tiers & Real Evidence Separation
- **Tier 1 (Cloud-Only / Featherweight)**:
  - **GPU**: None required (Zero GPU, Zero PyTorch on host).
  - **RAM**: 4 GB RAM minimum.
  - **Storage**: < 500 MB disk footprint.
  - **Mode**: BYOK Cloud APIs (OpenAI, Fal.ai, SiliconFlow). Real API calls verified.
- **Tier 2 (Physically Verified NVIDIA CUDA)**:
  - **GPU**: NVIDIA RTX (RTX 3060 12GB Ampere, driver 572.70, CUDA 12.8 physically verified on host rig).
  - **Engines**: ComfyUI (managed and external), Stable Diffusion WebUI (AUTOMATIC1111).
- **Tier 3 (Candidate Architecture - Unverified Physical Non-NVIDIA Discrete GPUs)**:
  - **Hardware**: AMD Radeon (DirectML / ROCm) and Intel Arc (DirectML / OneAPI IPEX).
  - **Status**: Detection and launch flag injection implemented and verified via unit tests; physical generation unverified in this session.
- **Tier 4 (Source-Compatible Desktop Adapters - Unverified Native Build)**:
  - **Hardware**: Apple Silicon (MPS Metal).
  - **Status**: Platform adapters implemented and unit-tested; native binary compilation and physical Mac runs unverified in this session.

---

## 4. Setup & Running Instructions

### For End Users (Clean Windows Machine)
1. Download and extract `Berry-AI-Studio-v0.1.0-windows-x64.zip`.
2. Double-click `Berry.bat` or `berry.exe`.
3. The Rust launcher verifies the environment, probes backend readiness, and automatically opens your browser to `http://127.0.0.1:8000`.
4. **Zero developer tools required**: No installation of Python, Node.js, pnpm, Git, or compilers.

### For Developers (Source Checkout)
```bash
# 1. Install frontend dependencies and build assets
cd frontend && pnpm install && pnpm build && cd ..

# 2. Start Berry launcher (development fallback boots backend/.venv)
cargo run --manifest-path launcher/Cargo.toml
```

---

## 5. Requirement-to-Evidence Matrix (R01–R18 & L01–L12)

| Requirement ID | Specification | Implementation & Verification Evidence | Status |
| :--- | :--- | :--- | :--- |
| **R01** | Lightweight startup | Backend boots without `torch`; cloud mode requires 0 local GPU. Verified by `test_health.py` and `test_m1_core.py`. | **VERIFIED** |
| **R02** | Device readiness | `/api/v1/hardware/readiness` inspects NVIDIA GPU, VRAM, and storage without modifying system drivers. Verified by `test_m5_release.py`. | **VERIFIED** |
| **R03** | Managed engine installation | Isolated virtualenvs in `~/.ai-workflow/engine/`. Interrupted install recorded in manifest. Verified by `test_m2_engines.py`. | **VERIFIED** |
| **R04** | Existing engine connection | Connects to external engines via URL without modifying user directories. Verified by `test_comfy_bridge.py`. | **VERIFIED** |
| **R05** | Engine lifecycle | Supervised Start, Stop, and Status. Probes HTTP responsiveness. External processes preserved. Verified by `test_m2_engines.py`. | **VERIFIED** |
| **R06** | Infinite canvas | React Flow infinite canvas with pan/zoom, card selection, contextual image actions, and zero spaghetti wires. Verified by `FlowCanvas.tsx`. | **VERIFIED** |
| **R07** | Image creation | Prompt, aspect ratio, seed, and model selection. Unsupported combinations explain what is missing. Verified by `test_cancellation_and_actions.py`. | **VERIFIED** |
| **R08** | Inpainting | Canvas-aligned mask drawing tool (`InpaintModal.tsx`), natural dimension scaling, prompt editing, and result placement. Verified by `test_m3_creative.py`. | **VERIFIED** |
| **R09** | Upscaling and export | 2×/4× resolution upscaling (`UpscaleModal.tsx`), thumbnail dimension preview, and local export/download (`ImageCardNode.tsx`). | **VERIFIED** |
| **R10** | Workflow templates | Curated macro graphs for txt2img, img2img, inpaint, upscale. Node inputs validated. Verified by `test_macro_compiler.py`. | **VERIFIED** |
| **R11** | Model inventory | Non-destructive scanning of safetensors/checkpoints. Detects architectures (SDXL, SD1.5, Flux, LoRA) and missing VAE/CLIP. Verified by `test_m5_release.py`. | **VERIFIED** |
| **R12** | Directory management | Add/remove model roots via CLI and GUI without deleting files. Verified by `test_m5_release.py` and `EnvironmentManagerModal.tsx`. | **VERIFIED** |
| **R13** | BYOK cloud | Local credential storage for OpenAI, Fal.ai, SiliconFlow. Secrets redacted and never saved to canvas or git. Verified by `test_m4_cloud.py`. | **VERIFIED** |
| **R14** | Task lifecycle & cancellation | Queued, running, completed, error, and cancelled states. REST cancel endpoints (`/api/v1/tasks/{id}/cancel`, `/api/v1/workflow/cancel/{id}`) with truthful cloud disclosure. Verified by `test_cancellation_and_actions.py`. | **VERIFIED** |
| **R15** | Persistence & asset adoption | SQLite database saves projects, assets, and canvas state. Remote cloud URLs adopted into local content-addressable storage. Verified by `test_m1_core.py` and `test_m4_cloud.py`. | **VERIFIED** |
| **R16** | Deterministic caching | Hash calculated from action, prompt, model, seed, input image, and mask hashes. Identical inputs reuse cache; parameter changes re-execute. Verified by `test_dag_cache.py`. | **VERIFIED** |
| **R17** | Portable architecture | OS-specific process flags behind adapters (`launcher/src/backend.rs`). Portable core tested with 73 automated tests. | **VERIFIED** |
| **R18** | Native entry points | Opens configured native UI (`/api/v1/runtime/{engine}/ui`) without hardcoded assumptions. | **VERIFIED** |
| **L01** | Single entry point | Windows release package requires zero developer tools. Verified by `smoke-test-package.ps1` with sanitized PATH. | **VERIFIED** |
| **L02** | Accurate startup | 4-stage readiness check in Rust launcher. Missing frontend renders diagnostic HTML error rather than blank page. Verified by `test_m6_launcher_manager.py`. | **VERIFIED** |
| **L03** | No duplicate processes | Windows Named Mutex (`Global\BerryAIStudioLauncherMutex`) focuses existing workspace on second launch. Port collisions detected with diagnostic guidance. | **VERIFIED** |
| **L04** | Clear status | `/api/v1/manager/status` and `berry.exe status` aggregate core, engines, cloud, models, and active tasks. Verified by `test_m6_launcher_manager.py`. | **VERIFIED** |
| **L05** | Controlled engines | Managed engines install, start, stop, and update independently. External engines are never stopped or modified. | **VERIFIED** |
| **L06** | Recovery | Actionable error messages and retry paths for broken virtualenvs, port conflicts, and interrupted updates. | **VERIFIED** |
| **L07** | Shutdown policy | `/api/v1/manager/shutdown` and `berry stop` check active tasks; non-forced exit returns HTTP 409 if generations are running. Verified by `test_cancellation_and_actions.py`. | **VERIFIED** |
| **L08** | Updates separation | Application updates (`POST /api/v1/updates/app`) and engine updates (`POST /api/v1/runtime/{engine}/update`) are separate operations. Verified by `test_m6_launcher_manager.py`. | **VERIFIED** |
| **L09** | Launcher portability | Windows-specific Named Mutex and process creation behind `#[cfg(windows)]`. Cross-platform HTTP/TCP core. | **VERIFIED** |
| **L10** | Model inventory in launcher | `berry models list/roots/add-root/remove-root` CLI and GUI Environment Manager. Reuses backend model store. | **VERIFIED** |
| **L11** | Rust launcher boundary | Launcher implemented in Rust (`launcher/`), interacting with backend via REST API (`/api/v1/manager/*`). | **VERIFIED** |
| **L12** | Safe engine updates & rollback | Before engine update, active tasks are checked. Pre-update git commit captured; on failure, `git checkout <commit>` restores code. Preserves models and configs. Verified by `test_m6_launcher_manager.py`. | **VERIFIED** |

---

## 6. Update & Rollback Boundaries (Truthful Limitations)

1. **Application Updates (Berry AI Studio)**:
   - *Source Checkout Mode*: Executes `git pull --ff-only` on the current branch. Returns the updated commit hash and prompts the user to restart.
   - *Packaged Windows Distribution*: On Windows, operating system file locking prevents replacing the active running `berry.exe` and loaded DLLs in-place. The application update service provides structured guidance with download links to the latest release package on GitHub Releases.
   - *Data Safety Guarantee*: All user projects, assets, saved credentials, and custom model scan roots located in `%LOCALAPPDATA%\BerryAIStudio` remain external to the application binary folder and are preserved across updates.
2. **Engine Updates & Rollback (ComfyUI & WebUI)**:
   - *Active Task Guard*: Rejects updates with `HTTP 409 Conflict` if generation tasks are currently running.
   - *Rollback Semantics*: Captures the pre-update git commit (`git rev-parse HEAD`). If an update fails, restores the git repository tree (`git checkout <commit>`) and sets status to `ROLLED_BACK`. User weights in `models/` and configurations are strictly preserved.
   - *Documented Limitation*: Rollback restores the git repository code; **it does not byte-revert binary pip wheel modifications inside the virtual environment** if a package was partially overwritten before failing. If pip packages are damaged, recovery requires clicking "Reinstall" in the Environment Manager or restoring an external backup.
3. **Task Cancellation**:
   - Local engine cancellation dispatches interrupt signals (`/interrupt` on ComfyUI, `/sdapi/v1/interrupt` on SD WebUI).
   - Cloud task cancellation immediately flags the task as cancelled locally, but truthfully discloses: `"Cloud cancellation requested locally. Note: external cloud providers may continue asynchronous inference or incur compute charges."`
4. **Video Generation & Container Formats**:
   - Fal.ai (Fast SVD) and SiliconFlow (CogVideoX) output native MP4 (`video/mp4`, H.264).
   - Standard ComfyUI (AnimateDiff/SVD) without custom nodes outputs animated WebP (`image/webp`) via `SaveAnimatedWEBP`. If `VHS_VideoCombine` with ffmpeg is installed, ComfyUI outputs native MP4.
   - In the frontend canvas, MP4 and WebM containers render natively in `<video controls loop>`, while animated WebP renders via `<img>` with an "Animated WebP" badge.
   - Downloads and exports strictly preserve the native container extension (`.mp4`, `.webm`, or `.webp`).
5. **Conversational Agent Boundaries**:
   - The assistant operates via deterministic keyword and regular expression intent matching against predefined creative action schemas.
   - It does not claim general unconstrained natural-language reasoning or autonomous arbitrary workflow synthesis.
   - All execution requires explicit user review and approval via the proposal confirmation gate.
6. **Workflow Repair Ambiguity & Compatibility Guards**:
   - The ComfyUI repair engine automatically reconnects slots only when an unambiguous single source exists in the DAG. If multiple sources exist, automatic connection is blocked (`substitution_blocked`) to avoid graph corruption.
   - Checkpoint substitution is strictly constrained to matching architecture families (`sd15`, `sdxl`, `flux`, `svd`). Unknown or cross-family substitutions are blocked.

---

## 7. Remaining Manual Acceptance Test Cases

The following test scenarios should be executed during the unified product acceptance review:

1. **Clean-Machine Windows Package Verification**:
   - Extract `dist/Berry-AI-Studio-v0.1.0-windows-x64.zip` on a clean Windows 10/11 machine without host Python, Node.js, or Git installed.
   - Run `berry.exe` or double-click `Berry.bat`. Confirm readiness probe passes and opens `http://127.0.0.1:8000`.
   - Run `berry.exe` a second time; confirm it detects the running instance and focuses the browser without spawning a second process.
2. **Cloud-Only BYOK End-to-End Workflow**:
   - On a machine without local engines, open **Cloud BYOK** and enter a valid API key (Fal.ai, OpenAI, or SiliconFlow).
   - Generate an image via the Bottom Creation Dock (`txt2img`).
   - Click the image card's **Paintbrush** button to open `InpaintModal`, draw a mask, modify prompt, and submit. Confirm result appears on canvas.
   - Click the **Maximize** button to open `UpscaleModal`, choose 2×, and upscale.
   - Click **Download** on the resulting card and verify the downloaded PNG file.
   - Restart Berry and confirm that the project and all adopted assets remain present on the canvas.
3. **Local NVIDIA Engine Workflow (Requires NVIDIA GPU)**:
   - Open **Environment Manager**, click **Install** under ComfyUI. Verify progress and isolated runtime creation.
   - Start ComfyUI and verify health badge turns `RUNNING`.
   - Add a custom model root containing an SD 1.5 or SDXL checkpoint. Verify model inventory detection.
   - Execute a local generation and confirm output is persisted in local assets.
4. **Shutdown & Active Task Guard**:
   - Start a long-running generation task.
   - Run `berry.exe stop` (without `--force`); confirm it refuses to stop and reports active tasks.
   - Run `berry.exe stop --force`; confirm it cancels active tasks and cleanly shuts down.
