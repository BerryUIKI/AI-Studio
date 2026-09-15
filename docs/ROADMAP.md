# Project Roadmap & Milestones

This roadmap outlines the phased development path for **AI-Workflow**, moving from a lightweight MVP to a multi-modal, dual-engine production studio.

---

## Milestone 1: MVP Core ✅ (Active)
*Goal: Deliver a lightning-fast visual canvas that executes cloud-based multimodal workflows with zero local GPU setup.*

- [x] Initial repository setup & engineering governance documentation.
- [x] Git branching model (`main` release, `dev` integration) and CI standards.
- [x] Frontend ReactFlow canvas implementation with dark-mode aesthetic (`@xyflow/react`, Tailwind CSS, Zustand state management).
- [x] Base node library (Pydantic v2 schemas, in-memory registry, REST endpoint `/api/v1/nodes`):
  - `input.text` — Text / Prompt Input
  - `text.llm` — LLM Prompt Expander (OpenAI / DeepSeek / SiliconFlow compatible)
  - `image.generate` — Cloud Image Generator (FLUX / SDXL via Fal.ai or SiliconFlow)
  - `output.preview` — Media Preview Card
- [x] Core DAG engine with topological sorting (Kahn's algorithm) and cycle detection.
- [x] Deterministic dirty-checking and output caching via SHA-256 node hashing (`/api/v1/workflow/plan`).
- [x] **Cloud API execution runner** (`api_runner.py`): OpenAI-compatible LLM, FLUX/SDXL/DALL-E image, and passthrough input drivers.
- [x] **WebSocket real-time streaming** (`/ws/workflow/run`): Streams `NodeStatus`, `NodeOutput`, `GraphFinished` events to the canvas.
- [x] **Single-node isolated execution**: `▶ Run this node` wired via WebSocket with upstream dependency auto-resolution.

> **Milestone 1 is complete.** 14/14 backend tests passing. Frontend canvas renders live status badges.


---

## Milestone 2: ComfyUI Bridge & Isolated Sandboxed Runtime ✅ (Complete)
*Goal: Provide seamless local acceleration without UI spaghetti or host environment pollution.*

- [x] **External ComfyUI bridge driver** (`comfy_runner.py` connecting to `http://localhost:8188` with health probes & model discovery).
- [x] **Subgraph Macro Compiler** (`macro_compiler.py`):
  - Automatically translates high-level `image.comfy.txt2img` node into ComfyUI's 6-node prompt DAG (Checkpoint, EmptyLatent, CLIP Pos/Neg, KSampler, VAE, SaveImage) with optional LoRA chaining.
- [x] **In-App Isolated ComfyUI Runtime Supervisor** (`supervisor.py`):
  - Hermetic application directory layout (`~/.ai-workflow/engine/` or `%LOCALAPPDATA%/AI-Workflow/engine/`).
  - Background process supervisor with PID tracking, graceful shutdown, and zero host environment pollution.
- [x] **Mixed-mode workflows on Canvas**:
  - Cloud LLM for scripting + Local ComfyUI for image rendering on the same canvas.
  - WebSocket streaming execution, real-time node badges, and output image previews.

> **Milestone 2 is complete.** 28/28 backend tests passing. Frontend production build verified.

---

## Milestone 3: Multimodal Expansion & Flow Logic
*Goal: Support complete multimedia creation pipelines (Audio, Video, Batch data).*

- [ ] Voice synthesis node (ElevenLabs / CosyVoice / Azure Speech API).
- [ ] Video generation node (Kling, Runway Gen-3, Luma Dream Machine API).
- [ ] Universal HTTP / Webhook node (call arbitrary REST endpoints with JSONPath extraction).
- [ ] Batch processing & Table input node (generate variations across CSV/JSON rows).
- [ ] Storyboard View (timeline-based sequential layout for video and storyboard creators).

---

## Milestone 4: Ecosystem, Templates & Desktop Packaging
*Goal: Enable frictionless sharing and one-click desktop distribution.*

- [ ] Workflow preset library (one-click import of pre-built production workflows).
- [ ] Community export/import format (`.flow.json`) with asset bundling.
- [ ] Lightweight cross-platform desktop application packaging via **Tauri** (Windows, macOS, Linux).
- [ ] Granular API token usage metrics and cost estimation calculator.
