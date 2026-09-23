# Coding Agent Handoff

Copy the prompt below into a coding-agent task with access to this repository and these documents.

---

You are implementing Berry AI Studio as a senior product engineer. The product owner has approved the first-release direction and scope documented in this repository. Proceed with implementation in incremental, verifiable milestones.

## Read First

1. AGENTS.md, BRANCHING_STRATEGY.md and CONTRIBUTING.md.
2. docs/PRODUCT_VISION.md.
3. docs/PRD.md.
4. docs/ARCHITECTURE.md.
5. docs/ROADMAP.md.
6. docs/PRODUCT_ALIGNMENT.md for discussion history and known prototype gaps.

The vision and PRD contain the current product scope. The architecture provides implementation guidance. Older prototype behavior does not override these documents. Follow current user instructions and repository rules; distinguish accepted scope from unresolved engineering choices.

## Build This Product

Berry is a beginner-friendly AI creative workspace with its own infinite canvas as the primary interface. Users select assets and invoke actions without learning low-level node wiring.

First release:
- Windows distribution, cross-platform code from the beginning.
- NVIDIA local generation plus cloud-only creation using user-provided API keys.
- Optional isolated ComfyUI and Stable Diffusion WebUI installation, connection to existing installations, lifecycle/health guidance, and native UI entry points.
- Text-to-image, image-to-image, inpainting and upscaling.
- Curated existing ComfyUI workflows with validated dependencies and explicit input/output mappings.
- Local model scanning/import, directory management, compatibility and missing-dependency information.
- Persistent projects, canvas layouts, assets and generation history.
- Truthful task status, cancellation, retry and deterministic caching.

Do not implement video, Agents, unspecified CLI features, non-NVIDIA inference, platform billing, marketplaces or team collaboration in this release. Do not interpret later non-NVIDIA discrete GPU support as a requirement for CPU, integrated GPU or NPU inference.

## Starting State and Cautions

This handoff was prepared on feature/berry-product-alignment, based on origin/dev. Product naming/documentation edits are currently uncommitted. Inspect git status and diffs before changing branches or committing; preserve and incorporate these edits. Do not reset the worktree or overwrite user changes. For a fresh checkout, ensure the entire documentation/naming patch is present first.

At review time, main contained only initial documentation while dev contained the prototype. Inspect current refs rather than assuming this remains true. Branch from dev according to repository rules and target dev for PRs. Never commit directly to main. Do not merge or publish a release unless separately requested.

All project documentation, code comments, issues, PRs, commit messages and release notes must be English. User discussion may be Chinese.

Known prototype problems to verify and repair:
- Single-node buttons invoke the whole graph.
- ComfyUI reports completion using a fabricated filename without retrieving actual output.
- Cache keys lose port binding identity and use upstream computation keys rather than output content.
- output.preview lacks an execution handler.
- Errors can allow dependent execution and inconsistent frontend state.
- Runtime supervision falls back to host Python and has no complete installer.
- Projects/assets are not durably managed.
- Frontend typing/styling and documented CI checks are incomplete.

No builds, tests, real API runs or hardware validation were performed during the planning handoff. Do not repeat historical passing-test claims as your own evidence.

## Execution Instructions

Start with M0, then follow the milestone gates. Resolve routine engineering choices yourself and record the rationale. Use current official engine/provider documentation for integration-specific behavior. Keep changes focused and preserve useful existing code.

Maintain the cloud-only lightweight core, five execution port types, isolated environments and semantic caching. Keep raw engine mechanics off the primary canvas. Never install dependencies globally or silently take ownership of user installations.

Treat all four image actions as product-level requirements, with an honest per-engine/provider capability matrix. Obtain real outputs and persist them before success. Never use mock output as a production substitute.

Add meaningful tests for DAG/cache changes, state transitions, persistence, isolation and adapters; validate UX and real integrations separately. Record exact commands and results. If hardware, credentials, network permissions or authorized API spend are missing, finish independent work and identify the precise remaining validation blocker.

Do not silently reduce approved scope to claim completion. Ask only when an unresolved choice materially changes scope, cost, privacy or irreversible user-data behavior. Do not seek renewed approval for already accepted product decisions.

For each milestone, report what changed, requirement IDs covered, verification performed, limitations and the next gate. Maintain an English requirement-to-test mapping. At final handoff, provide changed files, run/setup instructions, test evidence, actual supported integration versions and unresolved release blockers.

Begin by inspecting the worktree and reading the documents, then establish the baseline and implement M0/M1.
