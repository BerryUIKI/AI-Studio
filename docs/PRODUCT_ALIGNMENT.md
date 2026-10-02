# Berry AI Studio Product Alignment

Updated: 2026-09-23. Status: product direction and first-release scope approved. See PRODUCT_VISION.md and PRD.md for the current implementation baseline.

## Confirmed Decisions

- Product name: **Berry AI Studio**. Repository: `BerryUIKI/AI-Studio`.
- The user defines requirements and goals. The assistant acts as CTO and product manager, assessing scenarios, tradeoffs, feasibility, and acceptance criteria.
- Align requirements and long-term goals, write the specifications, and then develop features.
- Follow current AGENTS.md constraints: high-level nodes, five port types, API-first operation, optional isolated local engines, and deterministic caching.
- Product-facing names have been updated. Internal package names, service identifiers, environment variables, and engine directories remain unchanged pending a migration plan.
- All project documentation, PR titles and descriptions, commit messages, issues, release notes, code comments, and other project-facing written artifacts must use English. User discussions may remain in Chinese.

## Confirmed Product Direction

Berry AI Studio is an all-in-one AI creative workspace for beginners. It helps users deploy Stable Diffusion WebUI and ComfyUI quickly and use them for image generation, video generation, and image editing.

- Support Stable Diffusion WebUI and ComfyUI. Exact WebUI repository, versions, and compatibility matrix require technical assessment.
- Provide an infinite canvas and unified model management; detailed interactions and scope remain open.
- Support existing ComfyUI workflows and, later, Agent-generated workflows.
- Include CLI-based and conversational generation. The meaning of CLI support and the tools involved remain to be clarified.
- Agent features may be scheduled later; they are not prerequisites for the initial creative workflow.
- The first release may target Windows only, but code must support cross-platform design from the outset. Other platform release and acceptance schedules remain open.
- Use Berry's own interface as the primary creative experience while retaining native ComfyUI and WebUI entry points. Native access does not imply a commitment to bidirectional editing synchronization.
- Initially prioritize NVIDIA GPU users while also supporting cloud creation. Cloud-only use must not require local generation engines.
- Consider inference on non-NVIDIA discrete GPUs later. Hardware coverage, inference backends, model support, and performance targets require evaluation; universal compatibility is not promised.

Images, video, and editing are product goals, not a commitment to ship everything in the first release. Review the former API-first node-editor positioning. Current AGENTS.md still requires a lightweight core, API-first operation, and optional local engines; future specifications must clarify deployment priorities and dependencies without making local engines mandatory for startup.

## First-Release Scope Approved After Discussion

The product owner accepted all five scope proposals and the first-use journey:

- Text-to-image, image-to-image, inpainting and upscaling; video and Agents deferred.
- Infinite canvas as the primary workspace, with selection-based actions and no required manual node wiring.
- Both managed engine installation and connection to existing ComfyUI/WebUI, installed only when needed.
- Local model scanning, importing, directory management, compatibility and missing-dependency guidance. Download integration remains to be defined.
- BYOK cloud creation with provider selection; platform billing deferred.

Approved first-use journey: device readiness, engine installation/connection, compatible model preparation, image generation, canvas selection and masked editing, upscaling/export, and project/history restoration after restart.

The user requested English specifications and a coding-agent handoff. See [Vision](PRODUCT_VISION.md), [PRD](PRD.md), [Architecture](ARCHITECTURE.md), [Roadmap](ROADMAP.md), and [Handoff](CODING_AGENT_HANDOFF.md). Detailed acceptance criteria and implementation defaults in those documents operationalize the approved scope; they are not evidence of completed development.

## Repository Snapshot

Remote updates were fetched and the repository inspected statically. At inspection, `main` contained initial documentation; `dev` contained a React/TypeScript canvas, FastAPI backend, and backend tests. `feature/berry-product-alignment` was created from `origin/dev` for naming and documentation changes.

The prototype includes node creation, connections, parameter editing, execution states, output previews, cloud text/image calls, DAG sorting and cycle detection, in-memory caching, ComfyUI integration, and process management. Historical roadmap completion marks do not establish product acceptance.

## Static Inspection Findings

1. **Single-node execution is incomplete.** `frontend/src/components/canvas/WorkflowNode.tsx` invokes whole-graph `runWorkflow()`. The WebSocket entry point does not accept a target node.
2. **Local generation does not await real results.** `backend/app/runners/comfy_runner.py` constructs a URL using `mock_filename` after submission and reports completion without waiting for actual output.
3. **Cache correctness is incomplete.** `backend/app/main.py` uses upstream computation keys instead of output hashes. `backend/app/core/cache.py` sorts parent hashes without port bindings, allowing incorrect reuse across different connections. Storage is in memory only.
4. **Preview execution is undefined.** `output.preview` is declared but lacks an execution handler.
5. **Failure behavior needs work.** Downstream execution may continue after failure while the frontend exits its executing state early. Define blocking, retries, cancellation, and partial success.
6. **Isolated setup is incomplete.** A supervisor exists but no installer was found. Missing isolated Python falls back to the current interpreter, conflicting with strict isolation goals.
7. **Core product flows remain incomplete.** Canvas state is not persisted. Project saving, assets, credential settings, import/export, and cost visibility do not form complete flows.
8. **Standards and implementation differ.** Frontend code uses `any` and inline styles. No CI configuration was found; some documented checks are not configured.

This review used static inspection and naming changes only. Dependencies were not installed, tests were not run, the app was not launched, and paid APIs were not called. Historical test results are not verification evidence for this review. Schedule fixes after requirements alignment.

## Remaining Decisions

First-release product scope is settled. Engineering decisions remain: exact engine versions and reference hardware, models/providers, desktop packaging, supported workflow import format, credentials and download UX. Resolve these with evidence during M0; do not reopen approved scope without a material reason.

Future CLI meaning and detailed long-term Agent/video/non-NVIDIA plans remain open and do not block the image release.

Keep approved requirements, engineering defaults, unverified implementation and future ideas distinct. All project-facing written artifacts must be English.
