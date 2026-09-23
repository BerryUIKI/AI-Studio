# Berry AI Studio Post-v0.1 Implementation Roadmap (M7–M12)

**Status**: Active Engineering Roadmap  
**Target Git Branch**: `dev`  
**Governing Documents**: [`docs/PRODUCT_VISION.md`](PRODUCT_VISION.md), [`docs/PRD.md`](PRD.md), [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/ROADMAP.md`](ROADMAP.md), [`docs/ACCEPTANCE_DOSSIER.md`](ACCEPTANCE_DOSSIER.md).

---

## 1. Executive Summary & Principles

This roadmap operationalizes the long-term approved technical directions for Berry AI Studio beyond v0.1:
1. **Video Generation**: Text-to-Video and Image-to-Video creation on the creative canvas.
2. **Unified Berry CLI**: Command-line creation and environment management sharing backend services.
3. **Conversational Agent Control**: Transparent workflow selection, parameterization, and gated execution.
4. **Agent Workflow Construction & Repair**: ComfyUI DAG parsing, validation, repair heuristics, and safe execution.
5. **Non-NVIDIA GPU Acceleration**: DirectML, ROCm, and OneAPI support for AMD Radeon and Intel Arc.
6. **Cross-Platform Desktop**: Native support and platform adapters for macOS (Apple Silicon Metal MPS) and Linux.

### Key Architectural Invariants:
- **No Silent Execution**: The Agent must always present the proposed workflow, model, expected external calls, and parameters for user inspection before execution.
- **5-Type Port Universal Contract**: Ports strictly adhere to `string`, `image`, `audio`, `video`, and `json`. Video assets conform to `video`.
- **Capability-Specific Boundaries**: Non-NVIDIA GPUs and additional OS targets are implemented via discrete adapters with documented reference devices. Untested combinations are labeled `Unverified / Experimental`.
- **Preserved v0.1 Baseline**: Cloud-only startup with zero PyTorch/GPU prerequisites remains intact; image journeys (txt2img, img2img, inpaint, upscale) remain fully functional.

---

## 2. Dependency-Ordered Milestones & Implementation Status

| Milestone | Title & Focus Area | Implementation PR | Status on `dev` | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **M7** | Video Generation & Usable Video Creation Journey | [PR #11](https://github.com/BerryUIKI/AI-Studio/pull/11) | **Merged** (`64cd55c`) | `test_m7_video.py` (7/7 passed), SVD XT / AnimateDiff macro compilers, Fal / SiliconFlow cloud video, canvas video cards |
| **M8** | Documented Unified Berry CLI for Creation & Management | [PR #12](https://github.com/BerryUIKI/AI-Studio/pull/12) | **Merged** (`8e394dd`) | `test_m8_cli.py` (3/3 passed), Rust tests (2/2 passed), `berry run/tasks/system`, [`docs/CLI_REFERENCE.md`](CLI_REFERENCE.md) |
| **M9** | Conversational Agent Control of Existing Workflows & Engines | [PR #13](https://github.com/BerryUIKI/AI-Studio/pull/13) | **Merged** (`1260722`) | `test_m9_agent.py` (6/6 passed), `AgentService`, transparent `AgentProposal`, human-in-the-loop gate, frontend `AgentPanel` |
| **M10** | Agent-Assisted Construction, Validation, Repair of Workflows | [PR #14](https://github.com/BerryUIKI/AI-Studio/pull/14) | **Merged** (`60c3620`) | `test_m10_workflow_repair.py` (6/6 passed), ComfyUI DAG syntax & port validator, automated heuristic repair engine |
| **M11** | Local Inference on Selected Non-NVIDIA Discrete GPUs | [PR #15](https://github.com/BerryUIKI/AI-Studio/pull/15) | **Merged** (`7f700b2`) | `test_m11_hardware.py` (4/4 passed), AMD/Intel/Apple GPU detection, DirectML flags, [`docs/SUPPORT_MATRIX.md`](SUPPORT_MATRIX.md) |
| **M12** | Cross-Platform Desktop Adapters (macOS Metal & Linux) | [PR #16](https://github.com/BerryUIKI/AI-Studio/pull/16) | **Merged** (`2551796`) | `test_m12_cross_platform.py` (4/4 passed), Unix domain socket single instance, cross-platform browser, [`docs/PLATFORM_PORTABILITY.md`](PLATFORM_PORTABILITY.md) |

---

## 3. Milestone Specifications

### M7: Video Generation & Creative Video Creation Workflow

- **User Journey**:
  - The user can trigger Text-to-Video (`txt2video`) from the creation panel.
  - The user can select any existing image card on the canvas and trigger Image-to-Video (`img2video` / "Animate Image").
  - Resulting video appears on the canvas with an embedded video player (play, pause, scrub, loop, volume), provenance metadata (model, seed, motion bucket, fps, duration), and one-click download/export (MP4/WebM).
- **Supported Capability Matrix**:
  - *Cloud BYOK Providers*:
    - Fal.ai: `fal-ai/fast-svd/image-to-video` (Stable Video Diffusion), `fal-ai/luma-dream-machine`, `fal-ai/kling-video`.
    - SiliconFlow: `siliconflow/cogvideox-5b` (Text-to-Video / Image-to-Video).
  - *Local ComfyUI*:
    - AnimateDiff SD1.5 / SDXL macro subgraphs (`AnimateDiffLoaderWithContext`, `KSampler`, `VHS_VideoCombine` / `SaveAnimatedWEBP`).
- **Technical Boundaries**:
  - Video port type conforms to the 5-type contract (`video`).
  - Output stored in `AssetStore` with media type `video/mp4`, `video/webm`, or `image/webp` (for animated WebP from standard ComfyUI). Content-addressed via SHA-256.
  - Video playback in GUI: native `<video>` for MP4/WebM containers; `<img>` with "Animated WebP" badge for animated WebP outputs.
  - Export: downloads preserve actual container extension (`.mp4`, `.webm`, or `.webp`).
  - Deterministic dirty-check caching accounts for video-specific parameters: `motion_bucket_id`, `fps`, `num_frames`, `duration`.
- **Data & Project Compatibility**:
  - SQLite database persists video assets and execution records. Project schema v1 loads seamlessly; canvas renders video cards.
- **Acceptance Criteria**:
  - `POST /api/v1/creative/execute` with `action="txt2video"` or `"img2video"` executes and produces a valid video asset.
  - Video cards render in frontend and can be selected, moved, played, and exported.
  - Cancellation sends interrupts to ComfyUI and sets local cancel flags for cloud tasks.
- **Explicit Exclusions**:
  - Multi-track timeline video editing, audio mixing/dubbing, arbitrary frame interpolation.

---

### M8: Documented Unified Berry CLI for Creation & Environment Management

- **User Journey**:
  - Developers and automation scripts can invoke Berry from the terminal:
    - `berry run txt2img --prompt "A serene forest" --output ./forest.png`
    - `berry run img2video --image ./input.png --prompt "Gentle camera pan" --output ./anim.mp4`
    - `berry tasks [list|status <id>|cancel <id>]`
    - `berry models [list|rescan|add-root|remove-root]`
    - `berry engines [list|start|stop|install|update]`
    - `berry system info`
- **Supported Capability Matrix**:
  - All creative actions (`txt2img`, `img2img`, `inpaint`, `upscale`, `txt2video`, `img2video`).
  - Engine lifecycle and model inventory inspection.
  - Plain text human output or machine-parseable JSON (`--json`).
- **Technical Boundaries**:
  - Implemented in Rust launcher (`launcher/src/main.rs` & `launcher/src/cli.rs`).
  - Communicates over HTTP with the local backend REST API; starts ephemeral worker if backend is not already active.
  - Shares the exact same services: `CreativeRunner`, `AssetStore`, `DatabaseManager`, `EngineSupervisor`.
- **Data & Project Compatibility**:
  - CLI tasks are registered in SQLite database and appear in GUI history.
- **Acceptance Criteria**:
  - CLI commands execute and return exit code 0 on success, non-zero on error.
  - Output image/video files written to requested disk path.
  - Comprehensive documentation in [`docs/CLI_REFERENCE.md`](CLI_REFERENCE.md).
- **Explicit Exclusions**:
  - Interactive Terminal UI (TUI) with curses/ratatui.

---

### M9: Conversational Agent Control of Existing Workflows & Engines

- **User Journey**:
  - The user chats with an Agent in a dedicated workspace panel: e.g. *"Create a photorealistic cyberpunk street scene at night in ComfyUI, high detail, then upscale 2x"*.
  - The Agent analyzes available engines, models, and cloud providers, and formulates a transparent **Action Plan**:
    - Target Engine / Provider (e.g. Local ComfyUI or Fal.ai)
    - Selected Model & Validated Workflow Template
    - Parameters (prompt, negative prompt, aspect ratio, steps, seed)
    - Expected external calls, estimated execution time, and cloud cost disclaimer.
  - The UI presents the plan with an **"Approve & Run"** button and editable fields.
  - The user can adjust parameters or approve execution; the Agent dispatches the action to `CreativeRunner` and presents results with next-step suggestions.
- **Supported Capability Matrix**:
  - Deterministic keyword and regex mapping to creative actions (txt2img, img2img, inpaint, upscale, txt2video, img2video).
  - Parameter extraction (aspect ratios, step count, seeds, engines) and template recommendation.
- **Technical Boundaries**:
  - Backend `AgentService` with rule-based and regex intent resolution; does not claim general unconstrained natural-language understanding or arbitrary workflow synthesis.
  - Strict human-in-the-loop gate: execution requires user approval token.
  - Transparent plan disclosure with cost, engine, and parameter visibility.
  - Never mutates engine files or executes uninspected external commands.
- **Data & Project Compatibility**:
  - Conversation sessions and generated proposals are persisted in project SQLite tables.
- **Acceptance Criteria**:
  - Agent parses user prompt into structured `AgentProposal` schema.
  - UI displays proposal, parameters, and confirmation dialog.
  - Execution only dispatches upon explicit user confirmation.
- **Explicit Exclusions**:
  - Unbounded conversational reasoning without explicit action templates; autonomous loop execution without user confirmation; silent billing against cloud accounts.

---

### M10: Agent-Assisted Construction, Validation, Repair, and Execution of ComfyUI Workflows

- **User Journey**:
  - Users can import complex ComfyUI workflows or ask the Agent to *"Diagnose why this workflow fails"*.
  - The Agent analyzes the ComfyUI DAG:
    - Validates node connections against port types (`MODEL`, `CLIP`, `VAE`, `LATENT`, `IMAGE`).
    - Checks for missing custom node classes and missing checkpoint/LoRA models.
    - Identifies topological cycles or disconnected subgraphs.
  - If errors exist, the Agent proposes a concrete **Repair Diff** (e.g. *"Node 8 (VAEDecode) is missing VAE input; connect from unambiguous Node 4 [slot 2]"*).
  - **Ambiguity Guards**: When multiple potential sources exist for an input slot (e.g., multiple VAE loaders or EmptyLatentImage nodes), automatic reconnection is blocked (`substitution_blocked`) rather than guessing, preventing corrupted dataflow.
  - **Model Family Guards**: Missing checkpoints are substituted only within the exact same architecture family (`sd15`, `sdxl`, `flux`, `svd`); cross-family or unknown substitutions are strictly blocked.
  - The user inspects the visual diff and accepts the repair.
  - Once validated, the workflow can be executed directly or registered into the `TemplateRegistry`.
- **Supported Capability Matrix**:
  - ComfyUI DAG syntax parser, topological sort cycle detector, and port type-checker.
  - Safe pattern repairs: unambiguous single-source slot reconnections, same-family model substitution.
  - Model dependency resolver: checks against indexed local models with family inference.
- **Technical Boundaries**:
  - Pure Python DAG analysis engine in `backend/app/core/workflow_validator.py` and `backend/app/core/workflow_repair.py`.
  - Sandboxed validation without running untrusted Python node code.
- **Data & Project Compatibility**:
  - Validated workflows can be saved as custom templates in `TemplateRegistry`.
- **Acceptance Criteria**:
  - Automated tests verify detection of broken connections, missing models, cycles, and type mismatches.
  - Repair engine fixes broken workflows safely and blocks ambiguous or cross-family mutations.
- **Explicit Exclusions**:
  - Arbitrary Python code execution inside custom nodes; automated downloading of untrusted git repositories; guessing ambiguous wiring.

---

### M11: Local Inference on Selected Non-NVIDIA Discrete GPUs

- **User Journey**:
  - Users with AMD Radeon or Intel Arc discrete GPUs run Berry AI Studio.
  - The Environment Manager detects the GPU hardware, reports detected VRAM, and displays the appropriate acceleration backend (DirectML / ROCm / OneAPI IPEX).
  - Engine supervisors automatically pass vendor-optimized launch flags to ComfyUI (e.g., `--directml`, `--use-split-cross-attention`, `--lowvram`).
  - Candidate configurations are clearly labeled as "Candidate Architecture (Unverified on Physical Hardware in Current Session)" with guidance to use Cloud BYOK if local performance is inadequate.
- **Supported Capability Matrix**:
  - *Candidate Reference Hardware*:
    - AMD Radeon RX 7900 XTX / 7800 XT / 6700 XT (Windows DirectML, Linux ROCm 6.x).
    - Intel Arc A770 / A750 (Windows DirectML, Linux IPEX/OneAPI).
  - *Status Classification*: Explicitly distinguished as "Verified on Physical Hardware" (NVIDIA CUDA) vs. "Candidate Architecture (Unverified on Physical Hardware in Current Session)" vs. "Experimental / DirectML Emulated".
- **Technical Boundaries**:
  - Extend `backend/app/runtime/hardware.py` to detect AMD GPUs via `rocm-smi` (Linux) and WMI `Win32_VideoController` (Windows), and Intel Arc GPUs via WMI.
  - Update `HardwareReadiness` schema with vendor classification (`nvidia`, `amd`, `intel`, `apple_silicon`, `cpu_only`).
  - Supervisor configures engine launch parameters dynamically based on detected GPU vendor.
- **Data & Project Compatibility**:
  - Fully backward compatible with existing NVIDIA and Cloud configurations.
- **Acceptance Criteria**:
  - Hardware detector correctly identifies AMD and Intel GPUs and reports VRAM.
  - Engine supervisor injects `--directml` or vendor flags when non-NVIDIA GPU is selected.
  - `docs/SUPPORT_MATRIX.md` documents verified vs. candidate and unverified combinations without claiming physical verification for unverified hardware.
- **Explicit Exclusions**:
  - Custom kernel compilation; driver installation scripts; claiming physical hardware verification without physical generation run logs.

---

### M12: Cross-Platform Desktop Adapters (macOS & Linux)

- **User Journey**:
  - macOS users (Apple Silicon M1/M2/M3/M4) and Linux users (Ubuntu 22.04+) can clone or download Berry AI Studio and launch the environment via `berry`.
  - On macOS, ComfyUI runs with Apple Silicon Metal Performance Shaders (`mps`) hardware acceleration.
  - On Linux, ComfyUI runs with native CUDA or ROCm.
  - Single-instance mutex safely prevents dual execution using cross-platform file locking (`flock`).
- **Technical Boundaries**:
  - Rust launcher updated with cross-platform single-instance mutex (`launcher/src/single_instance.rs` using `fs2` / Unix domain socket on non-Windows).
  - Process creation flags and browser launch commands abstract Windows (`cmd /c start`), macOS (`open`), and Linux (`xdg-open`).
  - Python resolution supports Unix paths (`runtime/python/bin/python`, `.venv/bin/python`).
- **Data & Project Compatibility**:
  - Project databases and asset files use relative paths and forward-slash normalization for portability across OS filesystems.
- **Acceptance Criteria**:
  - Launcher compiles cleanly and tests pass on `ubuntu-latest` and `macos-latest` in CI.
  - Backend test suite passes on Linux and macOS.
  - Hardware detector recognizes Apple Silicon Metal MPS and Linux GPU interfaces.
- **Explicit Exclusions**:
  - Apple Developer ID code notarization; Linux deb/rpm package building (portable source / tarball is the initial cross-platform scope).
