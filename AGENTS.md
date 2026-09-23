# AI Agent Guidelines & Coding Standards (AGENTS.md)

Welcome, AI Coding Agent (Antigravity, Claude Code, Cursor, GitHub Copilot, Devin, etc.). This document outlines the architectural invariants, operational rules, coding standards, and decision-making framework for working inside the **Berry AI Studio** repository.

---

## 1. Core Principles & Non-Negotiable Invariants

### Current Product Baseline

Read `docs/PRODUCT_VISION.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `docs/ROADMAP.md` before implementation. The primary canvas is a creative workspace with selection-based actions; users must not need to wire nodes to complete the image workflow. The five-type contract below applies to execution ports, not presentation objects. API-first preserves cloud-only operation while the first release also supports optional NVIDIA local engines. Do not treat historical prototype completion claims as product acceptance.

1. **Simplicity Over Exposing Internal Complexity**:
   - ComfyUI's greatest pitfall is user overwhelm (spaghetti wires, latent/clip/vae micro-management).
   - Our UI must expose only **high-level, human-understandable nodes** (e.g., "Generate Image", "Expand Prompt", "Upscale Image", "Remove Background").
   - **Never leak low-level execution details or raw tensor handles onto the canvas.**
2. **The 5-Type Port Universal Contract**:
   - Canvas ports must strictly conform to: `string`, `image`, `audio`, `video`, and `json`.
   - Any complex internal data representation must be encapsulated within the node or runner driver.
3. **API-First, Local-Optional**:
   - The primary application must run in a featherweight mode with zero GPU / PyTorch requirements, powered entirely by cloud APIs.
   - Local engine capabilities (e.g., ComfyUI execution) must always be optional, pluggable, and decoupled.
4. **Zero Host Pollution for Local Engines**:
   - Any local ComfyUI runtime installed by the app must live in an isolated directory (`~/.ai-workflow/engine/` or dedicated app runtime path) with a sandboxed virtual environment.
   - Never run global `pip install` commands that alter the host system's global Python environment.
5. **Deterministic Dirty-Check Caching**:
   - Every node execution is idempotent. Output must be cached by computing:
     $$\text{NodeHash} = \text{Hash}(\text{NodeType} + \text{Params} + \sum \text{UpstreamOutputHashes})$$
   - Never break or bypass this caching contract unless the user explicitly triggers a cache-bust.

---

## 2. Codebase Organization

```text
AI-Studio/
├── frontend/                     # React 18+ / Vite / Tailwind / @xyflow/react
│   ├── src/
│   │   ├── components/
│   │   │   ├── canvas/           # Flow canvas, custom node views, custom edges
│   │   │   ├── inspector/        # Node parameters & configuration inspector
│   │   │   ├── templates/        # Workflow preset gallery
│   │   │   └── ui/               # Reusable UI components (shadcn/ui style)
│   │   ├── stores/               # Zustand stores (flowStore, settingsStore, engineStore)
│   │   ├── types/                # Shared TypeScript contracts & schemas
│   │   └── api/                  # WebSocket & REST clients
├── backend/                      # Python (FastAPI / Pydantic / AsyncIO)
│   ├── app/
│   │   ├── core/                 # DAG parser, topological sort, hash engine, runner router
│   │   ├── nodes/                # Declarative node registries (text, image, audio, video)
│   │   ├── runners/              # Execution drivers:
│   │   │   ├── api_runner.py     # Unified cloud API caller (OpenAI, Fal, SiliconFlow)
│   │   │   └── comfy_runner.py   # ComfyUI WebSocket & REST API adapter
│   │   ├── runtime/              # Sandboxed ComfyUI installer, process supervisor & health-checks
│   │   └── schemas/              # Pydantic models for workflows, nodes, and WebSocket events
│   └── tests/                    # Pytest test suites
├── docs/                         # In-depth architectural specifications & RFCs
├── AGENTS.md                     # This file
├── BRANCHING_STRATEGY.md         # Git branch rules (main=release, dev=integration)
├── CONTRIBUTING.md               # Human contributor guide
└── README.md                     # Project overview and quick start
```

---

## 3. How to Implement a New Node

When asked to implement a new node, follow this two-step design:

### Step 1: Declare the Specification (`backend/app/nodes/`)
Define ports using the 5 core data types and specify user-configurable parameters:

```python
from app.schemas.node import NodeDefinition, NodePort, DataType, ParameterDef

class FluxImageGenNode(NodeDefinition):
    type = "image.flux.schnell"
    title = "FLUX Image Generator"
    category = "image"
    description = "Generate high-speed images using FLUX.1 [schnell]"
    
    inputs = [
        NodePort(id="prompt", name="Prompt", type=DataType.STRING, required=True),
        NodePort(id="ref_image", name="Reference Image", type=DataType.IMAGE, required=False)
    ]
    outputs = [
        NodePort(id="image", name="Output Image", type=DataType.IMAGE)
    ]
    parameters = [
        ParameterDef(name="aspect_ratio", label="Aspect Ratio", type="select", 
                     options=["1:1", "16:9", "9:16"], default="1:1"),
        ParameterDef(name="steps", label="Inference Steps", type="number", default=4)
    ]
```

### Step 2: Implement the Runner Execution Handler
Implement an asynchronous handler that yields streaming progress:

```python
async def execute_flux_node(inputs: dict, params: dict, context: ExecutionContext) -> dict:
    prompt = inputs["prompt"]
    # Call Cloud API or route to Local Comfy depending on configuration
    result_image_url = await context.api_client.generate_image(
        model="flux-schnell",
        prompt=prompt,
        aspect_ratio=params.get("aspect_ratio", "1:1")
    )
    return {"image": result_image_url}
```

---

## 4. Coding Conventions & Best Practices

### Project Language
- All project documentation, PR titles and descriptions, commit messages, issues, release notes, code comments, and other project-facing written artifacts must use English.
- Discussions may use the user's preferred language; record their outcomes in English in the repository.

### Python (Backend)
- **Runtime**: Python 3.10+ required.
- **Async First**: Use `async`/`await` and `httpx.AsyncClient` for all I/O, API calls, and WebSockets. Never block the event loop with synchronous network or disk calls.
- **Strict Typing**: All functions must have type hints. Validate payloads with Pydantic v2.
- **Linters/Formatters**: Format with `ruff` or `black`. Adhere to PEP 8.

### TypeScript / React (Frontend)
- **Strict TypeScript**: No `any` types unless strictly interfacing with legacy untyped third-party libraries.
- **State Management**: Use Zustand for global UI & canvas state. Keep component-local state inside React hooks.
- **Styling**: Tailwind CSS exclusively. Do not write arbitrary inline styles (`style={{ ... }}`). Use `clsx` or `cn()` utility for conditional classes.
- **Canvas Nodes**: Extend the base node wrapper to guarantee uniform node borders, status badges (Running, Cached, Error), and execution buttons.

---

## 5. Git & Branching Rules for Agents

- **GitFlow**: Follow `BRANCHING_STRATEGY.md`. Feature, ordinary bug-fix, and documentation branches start from and target `dev`; release branches start from `dev` and target `main`, then synchronize back to `dev`; hotfix branches start from `main` and target `main`, then synchronize back to `dev`. Never commit directly to `main` or `dev`.
- **Commit Messages**: Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- **Clean Commits**: Keep changes atomic. Do not bundle formatting refactors with behavioral feature additions.

---

## 6. Agent Do's and Don'ts Checklist

- [x] **DO** maintain the lightweight experience: Ensure the app boots fast without requiring torch or local GPU dependencies.
- [x] **DO** implement fallback and health-check handling for all external APIs and local ComfyUI endpoints.
- [x] **DO** write unit tests for DAG cycle detection and hash computation when modifying the core engine.
- [ ] **DON'T** expose raw ComfyUI latent IDs or tensor pins to the frontend canvas.
- [ ] **DON'T** hardcode API keys or sensitive endpoints. Always read from environment variables or UI secrets configuration.
- [ ] **DON'T** modify global user files outside the repository or the designated isolated application data directory.
