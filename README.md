# Berry AI Studio

A beginner-friendly AI creative workspace combining an infinite canvas, local generation engines, cloud creation, model management, and persistent projects.

## Project Status

The product direction and first-release scope are approved. The repository contains an early prototype; the target capabilities below are not claims of completed implementation. See the documentation and milestone acceptance gates before assessing readiness.

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
