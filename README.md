# AI-Workflow

<div align="center">

<h3>A Lightweight, API-First Visual Canvas for Multimodal AI Workflows</h3>

<p>
  <b>Escape the spaghetti wires.</b> Create powerful text, image, audio, and video pipelines with high-level semantic nodes, smart caching, and zero hardware barriers.
</p>

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Branch: dev](https://img.shields.io/badge/integration_branch-dev-green.svg)](https://github.com/BerryUIKI/AI-Workflow/tree/dev)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![React 18+](https://img.shields.io/badge/react-18+-61dafb.svg)](https://react.dev/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

</div>

---

## 🌟 Why AI-Workflow?

ComfyUI is remarkably capable, but it was designed as a low-level PyTorch tensor assembly bench. Users are forced to manually wire Latents, VAEs, CLIP encodings, and Samplers just to generate a picture, requiring expensive 16GB+ GPUs and complex CUDA installations.

**AI-Workflow** provides a modern, intuitive alternative:

| Feature | ComfyUI | AI-Workflow |
| :--- | :--- | :--- |
| **User Interface** | Low-level tensor pipelines (10+ wires per step) | **High-level semantic nodes** (Prompt, Generate, Voice, Video) |
| **Connection Types** | Dozens of complex types (Model, Clip, Vae, Latent) | **5 Universal Types** (`string`, `image`, `audio`, `video`, `json`) |
| **Hardware Barrier** | Requires high-end GPU & CUDA setups | **Zero hardware barrier** (runs anywhere via Cloud APIs) |
| **Local Model Support** | Native, but prone to environment conflicts | **Optional & Sandboxed** (isolated runtime, zero system pollution) |
| **API Cost Optimization**| Re-executes from change | **Deterministic Dirty-Check Caching** (prevents redundant API spend) |
| **Installation Size** | 20 GB – 100 GB+ | **Lightweight Core** (< 100 MB) |

---

## 🚀 Key Highlights

- 🎨 **Figma-Grade Visual Canvas**: Built on modern web technologies with fluid zooming, smooth pan, and instant reactivity.
- ⚡ **API-First by Default**: Plug in your OpenAI, DeepSeek, Fal.ai, or SiliconFlow API keys and start creating immediately.
- 💰 **Smart Dirty-Check Caching**: Modify prompt #3 without re-paying for prompt #1 and #2. The engine only executes modified nodes.
- 🧩 **Isolated & Sandboxed ComfyUI Engine**: Want local GPU acceleration? Run or install an embedded, self-contained ComfyUI runtime directly through the app **without polluting your host operating system**.
- 🔄 **Macro Subgraph Compilation**: High-level nodes automatically compile into ComfyUI's underlying execution graphs behind the scenes.
- 📦 **Export & Share**: Share workflows as portable `.flow.json` files with your team.

---

## 🏛️ Architecture Overview

```
AI-Workflow/
├── frontend/                        # Vite + React 18 + TypeScript + @xyflow/react + Tailwind CSS
│   └── src/
│       ├── components/canvas/       # FlowCanvas, WorkflowNode, NodePalette
│       ├── stores/                  # Zustand canvas & engine state
│       └── types/                   # TypeScript contracts (NodeDefinition, DataType, etc.)
├── backend/                         # FastAPI + Pydantic v2 + AsyncIO
│   ├── app/
│   │   ├── core/                    # DAG Engine, SHA-256 Hash Cache, Runner Router
│   │   ├── nodes/                   # Node registry & built-in node definitions
│   │   ├── runners/                 # Cloud API Driver & ComfyUI WebSocket Bridge
│   │   ├── runtime/                 # Isolated ComfyUI Supervisor & Sandboxed Installer
│   │   └── schemas/                 # Pydantic models (NodeDefinition, WorkflowGraph, Events)
│   └── tests/                       # Pytest test suites (10 tests, 100% passing)
└── docs/                            # Architecture spec, Roadmap, RFCs
```

For complete technical details, see the [Architecture Document](docs/ARCHITECTURE.md).

---

## 🚦 Quick Start (Development)

### Prerequisites
- Node.js `18+` and `pnpm` (`npm install -g pnpm`)
- Python `3.10+`

### 1. Clone & Switch to Integration Branch
```bash
git clone https://github.com/BerryUIKI/AI-Workflow.git
cd AI-Workflow
git checkout dev
```

### 2. Launch the Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Launch the Frontend Canvas
```bash
cd ../frontend
pnpm install
pnpm approve-builds --all   # Required on first install to allow esbuild native binaries
pnpm dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🌿 Branching & Contribution Governance

To maintain production stability:
- **`main`**: Strictly protected release branch. Contains only stable, tagged releases (`vX.Y.Z`).
- **`dev`**: Active integration branch. **All PRs must target `dev`**.

Please consult:
- [BRANCHING_STRATEGY.md](BRANCHING_STRATEGY.md) for branch models and commit standards.
- [CONTRIBUTING.md](CONTRIBUTING.md) for setup and pull request workflows.
- [AGENTS.md](AGENTS.md) for guidelines tailored to AI coding assistants.
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community guidelines.

---

## 🗺️ Roadmap

Check our [Roadmap](docs/ROADMAP.md) for upcoming milestones including:
- Cloud multimodal drivers (FLUX, ElevenLabs, Kling, Runway)
- In-app isolated ComfyUI engine installer
- Tauri desktop packaging
- Community workflow templates

---

## 📄 License

Distributed under the **Apache License 2.0**. See [LICENSE](LICENSE) for more information.
