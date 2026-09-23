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

## 2. Dependency-Ordered Milestones

```
M0–M6 (v0.1 Integrated Baseline)
  │
  ▼
M7 — Video Generation & Usable Video Creation Journey
  │
  ▼
M8 — Documented Unified Berry CLI for Creation & Environment Management
  │
  ▼
M9 — Conversational Agent Control of Existing Workflows & Engines
  │
  ▼
M10 — Agent-Assisted Construction, Validation, Repair, and Execution of ComfyUI Workflows
  │
  ▼
M11 — Local Inference on Selected Non-NVIDIA Discrete GPUs
  │
  ▼
M12 — Cross-Platform Desktop Support (macOS Apple Silicon & Linux)
```

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
  - Output stored in `AssetStore` with media type `video/mp4` or `video/webm`, content-addressed via SHA-256.
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
  - Natural-language mapping to all creative actions (txt2img, img2img, inpaint, upscale, txt2video).
  - Intent classification, parameter extraction, and template matching.
- **Technical Boundaries**:
  - Backend `AgentService` with rule-based and LLM-assisted intent resolution.
  - Strict human-in-the-loop gate: execution requires user approval token.
  - Never mutates engine files or executes uninspected external commands.
- **Data & Project Compatibility**:
  - Conversation sessions and generated proposals are persisted in project SQLite tables.
- **Acceptance Criteria**:
  - Agent parses user prompt into structured `AgentProposal` schema.
  - UI displays proposal, parameters, and confirmation dialog.
  - Execution only dispatches upon explicit user confirmation.
- **Explicit Exclusions**:
  - Autonomous loop execution without user confirmation; silent billing against cloud accounts.

---

### M10: Agent-Assisted Construction, Validation, Repair, and Execution of ComfyUI Workflows

- **User Journey**:
  - Users can import complex ComfyUI workflows or ask the Agent to *"Add face detailing to my workflow"* or *"Diagnose why this workflow fails"*.
  - The Agent analyzes the ComfyUI DAG:
    - Validates node connections against port types (`MODEL`, `CLIP`, `VAE`, `LATENT`, `IMAGE`).
    - Checks for missing custom node classes and missing checkpoint/LoRA models.
    - Identifies topological cycles or disconnected subgraphs.
  - If errors exist, the Agent proposes a concrete **Repair Diff** (e.g. *"Node 8 (VAEDecode) is missing VAE input; connect from Node 4 [slot 2]"*).
  - The user inspects the visual diff and accepts the repair.
  - Once validated, the workflow can be executed directly or registered into the `TemplateRegistry`.
- **Supported Capability Matrix**:
  - ComfyUI DAG syntax parser, topological sort validator, and port type-checker.
  - Common pattern repairs: missing VAE decode, mismatched latent dimensions, missing LoRA bypass.
  - Model dependency resolver: checks against indexed local models.
- **Technical Boundaries**:
  - Pure Python DAG analysis engine in `backend/app/core/workflow_validator.py` and `backend/app/core/workflow_repair.py`.
  - Sandboxed validation without running untrusted Python node code.
- **Data & Project Compatibility**:
  - Validated workflows can be saved as custom templates in `TemplateRegistry`.
- **Acceptance Criteria**:
  - Automated tests verify detection of broken connections, missing models, and invalid node types.
  - Repair engine fixes broken workflows and produces valid, executable graphs.
- **Explicit Exclusions**:
  - Arbitrary Python code execution inside custom nodes; automated downloading of untrusted git repositories.

---

### M11: Local Inference on Selected Non-NVIDIA Discrete GPUs

- **User Journey**:
  - Users with AMD Radeon or Intel Arc discrete GPUs run Berry AI Studio.
  - The Environment Manager detects the GPU hardware, reports detected VRAM, and displays the appropriate acceleration backend (DirectML / ROCm / OneAPI IPEX).
  - Engine supervisors automatically pass vendor-optimized launch flags to ComfyUI (e.g., `--directml`, `--use-split-cross-attention`, `--lowvram`).
  - Unsupported or untested configurations display clear performance caveats and recommendation to use Cloud BYOK if local performance is inadequate.
- **Supported Capability Matrix**:
  - *Reference Hardware*:
    - AMD Radeon RX 7900 XTX / 7800 XT / 6700 XT (Windows DirectML, Linux ROCm 6.x).
    - Intel Arc A770 / A750 (Windows DirectML, Linux IPEX/OneAPI).
  - *Status Classification*: Explicitly distinguished as "Verified on Reference Hardware" vs. "Experimental / DirectML Emulated".
- **Technical Boundaries**:
  - Extend `backend/app/runtime/hardware.py` to detect AMD GPUs via `rocm-smi` (Linux) and WMI `Win32_VideoController` (Windows), and Intel Arc GPUs via WMI.
  - Update `HardwareReadiness` schema with vendor classification (`nvidia`, `amd`, `intel`, `apple_silicon`, `cpu_only`).
  - Supervisor configures engine launch parameters dynamically based on detected GPU vendor.
- **Data & Project Compatibility**:
  - Fully backward compatible with existing NVIDIA and Cloud configurations.
- **Acceptance Criteria**:
  - Hardware detector correctly identifies AMD and Intel GPUs and reports VRAM.
  - Engine supervisor injects `--directml` or vendor flags when non-NVIDIA GPU is selected.
  - `docs/SUPPORT_MATRIX.md` documents verified vs. unverified combinations.
- **Explicit Exclusions**:
  - Custom kernel compilation; driver installation scripts; obsolete legacy GPUs lacking FP16 support.

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
