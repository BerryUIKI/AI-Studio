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
- [ ] **[In Progress]** Cloud API execution runner (`api_runner.py`) with OpenAI-compatible LLM & image API calls.
- [ ] Single-node isolated execution via `▶ Run this node` wired to execution runner.
- [ ] WebSocket real-time progress streaming from backend to canvas node status badges.

---

## Milestone 2: ComfyUI Bridge & Isolated Sandboxed Runtime
*Goal: Provide seamless local acceleration without UI spaghetti or host environment pollution.*

- [ ] External ComfyUI bridge driver (`comfy_runner.py` connecting to `http://localhost:8188`).
- [ ] Subgraph Macro Compiler:
  - Translate high-level `Local Txt2Img` node into ComfyUI's 6-node prompt graph automatically.
- [ ] In-App Isolated ComfyUI Runtime Installer:
  - Standalone virtual environment setup (using standalone `uv` / portable Python).
  - Background process supervisor (Start / Stop / Restart / Health Check).
  - Model directory mapping without copying gigabytes of duplicate files.
- [ ] Mixed-mode workflows: Cloud LLM for scripting + Local ComfyUI for image rendering on the same canvas.

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
