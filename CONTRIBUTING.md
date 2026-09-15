# Contributing to AI-Workflow

First off, thank you for considering contributing to **AI-Workflow**! Open-source thrives because of community members like you.

This document outlines the workflow and quality guidelines for contributing code, documentation, and workflow presets.

---

## Code of Conduct

All contributors and participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please report any unacceptable behavior to the project maintainers.

---

## Branching & Release Model

We strictly follow a structured Git branching strategy:
- **`main`**: The official, production-ready release branch. Direct commits are forbidden.
- **`dev`**: The active integration branch. **All feature and bug fix pull requests must target `dev`**.

Before opening a PR, please read our complete [Branching Strategy Specification](BRANCHING_STRATEGY.md).

---

## Development Environment Setup

### Prerequisites

- **Node.js**: `v18.0.0+` (or `v20.x` LTS recommended)
- **pnpm**: `v8.x` or `v9.x` (`corepack enable` or `npm install -g pnpm`)
- **Python**: `3.10+` or `3.12+`
- **uv** (recommended) or standard `venv`

### 1. Clone the Repository

```bash
git clone https://github.com/BerryUIKI/AI-Workflow.git
cd AI-Workflow
git checkout dev
```

### 2. Setup the Frontend

```bash
cd frontend
pnpm install
pnpm dev
```
The frontend canvas will be available at `http://localhost:5173`.

### 3. Setup the Backend

```bash
cd ../backend
python -m venv .venv

# On Windows pwsh:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
The backend API and WebSocket server will be available at `http://localhost:8000`.

---

## Contribution Workflow

1. **Check Issues**: Check existing GitHub Issues or start a discussion before making substantial architectural changes.
2. **Branch from `dev`**:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-awesome-feature
   ```
3. **Make Atomic Changes**:
   - Write clean, self-documenting code.
   - Maintain unit tests for new logic.
4. **Commit with Conventional Commits**:
   - Follow the standard format: `type(scope): description`.
   - Example: `feat(nodes): add ElevenLabs TTS voice synthesis node`
5. **Run Checks Locally**:
   - Frontend: `pnpm typecheck && pnpm lint`
   - Backend: `pytest` and `ruff check .`
6. **Open a Pull Request**:
   - Base branch: **`dev`**.
   - Fill out the PR template completely.
   - Link related issue numbers (e.g., `Fixes #42`).

---

## Design Philosophy

When contributing new nodes or canvas components, please keep our core tenets in mind:

- **Keep It Simple**: Never expose raw low-level tensor pipelines or complex mathematical node parameters on the main canvas.
- **Universal Types**: All node connections must utilize the 5 core types (`string`, `image`, `audio`, `video`, `json`).
- **Cost Awareness**: Respect user API tokens. Ensure nodes support dirty-checking and state caching.
- **System Isolation**: Any feature interacting with local ComfyUI must never pollute the host system's global environment.

---

## Pull Request Checklist

Before submitting your PR, ensure:
- [ ] PR targets the **`dev`** branch.
- [ ] All new and existing tests pass.
- [ ] Code adheres to TypeScript and Python formatting guidelines.
- [ ] User-facing features include updated documentation or tooltips.
- [ ] Commit history is clean and uses conventional commit messages.

Thank you for helping make AI creation accessible and enjoyable for everyone!
