# Berry AI Studio

A beginner-friendly AI creative workspace combining an infinite canvas, local generation engines, cloud creation, model management, and persistent projects.

## Project Status

The product direction and first-release scope are approved. The repository contains an early prototype; the target capabilities below are not claims of completed implementation. See the documentation and milestone acceptance gates before assessing readiness.

## Quick Start & Running the Desktop App

### 1. Launch Native Desktop App (Tauri, No Browser Required)
Double-click **`Berry.bat`** in the repository root:
```powershell
.\Berry.bat
```
Launches the standalone desktop application window (powered by Tauri & WebView2). No web browser tabs or command windows required.

### 2. Development Commands

```bash
# Install dependencies
pnpm install

# Frontend development
pnpm dev:web          # Start Vite dev server (frontend only at http://localhost:5173)
pnpm typecheck        # TypeScript type check
pnpm lint             # ESLint
pnpm test             # Vitest

# Desktop development (requires Rust toolchain)
pnpm tauri dev        # Start full Tauri desktop app with hot reload
pnpm tauri build      # Production build of the native desktop executable
```

---

## How to Compile & Build from Source

Berry AI Studio consists of four primary components:
1. **Frontend SPA** (React, TypeScript, Vite, Tailwind, React Flow)
2. **Native Rust Launcher & Supervisor** (`launcher/target/release/berry.exe`)
3. **Native Tauri Desktop Application** (`frontend/src-tauri/target/release/berry-app.exe`)
4. **FastAPI Backend Core** (`backend/app/main.py`)
5. **Embedded Local LLM Runtime** (`runtime/llama_server/llama-server.exe` based on [llama.cpp](https://github.com/ggml-org/llama.cpp))

### Prerequisites

| Tool | Recommended Version | Purpose |
| :--- | :--- | :--- |
| **Node.js & pnpm** | Node.js 18+ / pnpm 8+ | Frontend package management and Vite bundling |
| **Rust Toolchain** | Stable (`x86_64-pc-windows-msvc`) | Compiling `berry.exe` and Tauri desktop app |
| **Python** | Python 3.10 - 3.12 (64-bit) | Backend services, DAG runner, and supervisor |
| **WebView2** | Microsoft Edge WebView2 | Native desktop UI runtime (pre-installed on Windows 10/11) |

---

### Step-by-Step Compilation

#### 1. Compile the Frontend Web Assets
```powershell
# In the repository root:
pnpm install
pnpm build
```
This bundles the production web application into `frontend/dist/`.

#### 2. Compile the Native Rust Launcher (`berry.exe`)
The lightweight Rust launcher manages background startup, health probing, readiness checks, and process supervision:
```powershell
cd launcher
cargo build --release
cd ..
```
The compiled executable is placed at `launcher/target/release/berry.exe`.

#### 3. Compile the Native Tauri Desktop Window (`Berry AI Studio.exe`)
```powershell
cd frontend
pnpm tauri build
cd ..
```
*(Or compile directly via Cargo: `cd frontend/src-tauri && cargo build --release && cd ../..`)*.  
The compiled native executable is placed at `frontend/src-tauri/target/release/berry-app.exe`.

#### 4. Prepare the Backend Python Environment
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
cd ..
```

#### 5. Embedded LLM Engine Setup (`llama.cpp` / `llama-server`)
Berry AI Studio integrates `llama-server` (from [llama.cpp](https://github.com/ggml-org/llama.cpp)) as an isolated local LLM inference engine without external Ollama dependencies or host environment modifications:
- **Automatic 1-Click Install**: When starting the app, navigate to **Settings -> Models & Engines** or open the **Setup Wizard**, then click **"Install llama.cpp"**. Berry automatically fetches pre-compiled AVX2 / CUDA binaries into `runtime/llama_server/llama-server.exe`.
- **Manual / Custom Build**: Place pre-compiled or custom-built `llama-server.exe` into:
  ```text
  runtime/llama_server/llama-server.exe
  ```
- **Universal GGUF Model Directory**: Downloaded or imported GGUF models are stored under:
  ```text
  engine/models/llm/<model-name>.gguf
  ```
  These weights are universally accessible by both the embedded AI assistant and infinite canvas ComfyUI GGUF nodes with zero disk duplication.

---

### Automated One-Click Windows Release Packaging

To build a fully self-contained, zero-prerequisite portable release archive (`.zip`) that runs out-of-the-box on clean Windows systems with zero installed Python, Node.js, or Git:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-windows-release.ps1
```

This automated script:
1. Builds the Rust launcher (`berry.exe`) in release profile.
2. Builds the Tauri native desktop binary (`berry-app.exe` -> `Berry AI Studio.exe`).
3. Compiles the frontend assets (`frontend/dist/`).
4. Bundles the backend code and stages an isolated hermetic Python runtime into `runtime/python/`.
5. Stages the embedded `llama-server` runtime (`runtime/llama_server/`) if available.
6. Packages everything into `dist/Berry-AI-Studio-v<version>-windows-x64.zip`.


## First-Release Scope

- Windows release with cross-platform code architecture.
- NVIDIA local generation and cloud-only creation with user-provided API keys.
- Optional isolated ComfyUI and Stable Diffusion WebUI installation and existing-engine connections.
- Berry's own infinite canvas and creation controls, with native engine entry points retained.
- Text-to-image, image-to-image, inpainting, and upscaling.
- Local model scanning/import, directory management, compatibility and dependency guidance.
- Persistent projects, assets, generation records, and reliable task execution.

Video, Agent features, clarified CLI integration, non-NVIDIA discrete GPU inference, and additional OS releases belong to later phases.

## Documentation

| Document | Purpose |
| --- | --- |
| [Product Vision](docs/PRODUCT_VISION.md) | Approved positioning and product boundaries |
| [First-Release PRD](docs/PRD.md) | Requirements and release acceptance scenarios |
| [Architecture](docs/ARCHITECTURE.md) | Target technical design and invariants |
| [Roadmap](docs/ROADMAP.md) | Implementation milestones and evidence gates |
| [Product Alignment](docs/PRODUCT_ALIGNMENT.md) | Decision history and prototype inspection findings |
| [Coding Agent Handoff](docs/CODING_AGENT_HANDOFF.md) | Copyable implementation prompt |

## Development Foundation

The prototype uses React, TypeScript, Vite, Tailwind, Zustand and React Flow on the frontend, and FastAPI/Pydantic on the backend. Generation engines remain optional and isolated from the lightweight core.

For development setup, see [CONTRIBUTING.md](CONTRIBUTING.md). The setup instructions require validation against the implementation baseline; no build or runtime verification was performed during product planning.

## Contribution Rules

Branch from dev and target dev with pull requests. Never commit directly to main. Use English for all project-facing written artifacts and Conventional Commits for commit messages.

Read [AGENTS.md](AGENTS.md), [Branching Strategy](BRANCHING_STRATEGY.md), [Contributing](CONTRIBUTING.md), and [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).
