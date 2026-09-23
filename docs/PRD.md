# Berry AI Studio First-Release PRD

Date: 2026-09-23.
Status: product scope approved; the detailed requirements and acceptance criteria below operationalize that scope for implementation.
References: [Vision](PRODUCT_VISION.md), [Architecture](ARCHITECTURE.md), [Roadmap](ROADMAP.md).

## Scope

Ship a Windows creative application with a portable core, an infinite canvas, ComfyUI and Stable Diffusion WebUI integration, NVIDIA local execution, BYOK cloud execution, model management, and durable projects. Implement text-to-image, image-to-image, inpainting, and upscaling.

The first development slices may run through the existing browser UI. The release must provide a documented Windows launch/install experience that does not require beginners to run developer commands. Desktop packaging technology is an engineering decision, not a confirmed product dependency.

## Requirements and Acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| R01 | Lightweight startup and onboarding | On a machine without local engines, Berry opens and offers cloud setup or local engine setup. The core does not import or require torch. |
| R02 | Device readiness | Show OS, detected NVIDIA GPU/VRAM when available, storage availability, and actionable prerequisites. Missing/unsupported hardware must not block cloud mode. Do not silently modify system drivers. |
| R03 | Managed engine installation | Offer ComfyUI and Stable Diffusion WebUI separately. Show destination, required downloads, progress and errors. Isolate runtimes; interrupted installation must remain visibly incomplete and allow retry without damaging existing data. |
| R04 | Existing engine connection | Connect to a running engine or register an existing installation. Validate identity/readiness and expose native UI access. Do not overwrite or upgrade user-owned installations automatically. Document connection ownership and supported versions. |
| R05 | Engine lifecycle | Managed engines expose start, stop, status and useful diagnostics. Healthy means the service responds, not merely that a PID exists. Berry must not stop externally managed processes. |
| R06 | Infinite canvas | Pan/zoom, place imported images and generated results, select/move items, remove canvas items without implicitly deleting source files, and invoke creation actions from selection. The main workflow requires no manual node connections. |
| R07 | Image creation | Provide prompt, relevant basic controls, execution location, and model/template selection for text-to-image and image-to-image. Results appear on the canvas with their generation record. Unsupported combinations explain what is missing. |
| R08 | Inpainting | Let users define a mask on a selected image, edit its prompt, preview the source/mask, submit the task and retain the original alongside the edited result. Preserve image/mask alignment through resizing. |
| R09 | Upscaling and export | Upscale a selected image with supported settings, show resulting dimensions, retain the source, and export an accessible image file. Never report success before output is available. |
| R10 | Workflow templates | Provide curated ComfyUI templates for supported actions. Validate required nodes, models and parameters before execution. Existing workflows may be registered through a documented supported format and input/output mapping; do not promise arbitrary workflow compatibility. |
| R11 | Model inventory | Scan user-selected directories and import model files by reference or explicit copy. Track location, identity, category, engine compatibility and missing dependencies. Unknown compatibility must remain unknown rather than guessed. |
| R12 | Directory management | Add/remove library roots and rescan. Removing a root removes its index, not the original files. Avoid duplicate copies where an engine supports shared directories; do not assume every format works in every engine. |
| R13 | BYOK cloud | Users select a provider, store/test a key, see supported actions, and run cloud creation without local engines. Show when assets will be uploaded. Keys must not enter workflow files, exports, logs, or frontend persistent storage. |
| R14 | Task lifecycle | Show queued/running/progress where available/succeeded/failed/cancel-requested/cancelled states. Support cancellation, explicit retry and useful errors. Unsupported remote cancellation is disclosed; do not claim that charges or remote computation stopped. |
| R15 | Persistence | Save/reopen project canvas layout, asset references and generation history across app restart. Adopt generated assets into managed storage so expiring remote URLs do not become the only copy. Handle missing imported files clearly. |
| R16 | Reuse and variants | Unchanged execution reuses valid cached results; changing relevant input/parameters invalidates dependent results. A visible Generate again/New variation action explicitly changes seed or busts cache. Editing unrelated layout must not trigger inference. |
| R17 | Portable architecture | OS-specific paths, processes, installation and credential access sit behind adapters. Use portable core tests and CI on Windows plus a non-Windows OS; this does not imply non-Windows release support. |
| R18 | Native entry points | Open the correct configured native UI for each connected engine. Do not hardcode one local port or promise synchronization of edits made there. |

## Capability Coverage

The product exposes all four image actions. Each engine/provider advertises its actual capability matrix; controls cannot imply universal parity. Provide a verified local reference path and a verified cloud-only path covering the four actions, potentially using more than one selected provider. Both ComfyUI and WebUI must support installation/connection and verified Berry-driven generation before release.

If provider access or hardware prevents verification, mark the requirement blocked or unverified rather than weakening scope or declaring completion. Select and document reference models, versions and providers during the first milestone using current official documentation.

## Interface Structure

- Main workspace: infinite canvas, asset selection and contextual actions.
- Creation controls: prompts, basic parameters, templates and explicit engine/provider selection.
- Projects/assets: create, reopen, view history, and export.
- Models: local inventory, directories, compatibility and missing items.
- Engines/settings: installation, connections, status, diagnostics and credentials.
- Tasks: progress, errors, cancellation and completed results.

These define responsibilities, not a fixed visual design. Advanced parameters may be collapsed. Keep tensor mechanics and internal engine graph IDs off the primary canvas.

## End-to-End Release Scenarios

1. Clean Windows/NVIDIA setup: install one engine, prepare a documented model, generate, inpaint, upscale, export, restart and reopen.
2. Existing installations: connect ComfyUI and WebUI without modifying their environments; generate through Berry and open each native UI.
3. Cloud-only setup: no local engine or torch; configure BYOK providers, perform the reference image workflow, then reopen downloaded results.
4. Failure recovery: interrupted installation, missing model, invalid key, disconnected engine and failed generation produce actionable states without false success.
5. Persistence and caching: restart preserves project/history; identical execution reuses output; changed mask, model, input or port mapping cannot reuse incorrect output.
6. Cancellation: cancelling a local task and a cloud task produces truthful state and prevents late events from corrupting another task's result.
7. Model safety: scanning/removing library roots leaves originals intact and reports incompatible/unknown models accurately.

Record environment, engine/provider versions, model identity, commands, results and limitations. Mock tests supplement but do not replace real integration evidence.

## Deferred

Video generation/editing, Agent conversation and workflow construction/repair, CLI product features, non-NVIDIA discrete GPU inference, macOS/Linux distribution, managed cloud billing, collaboration, marketplaces, automatic bulk model downloads, and arbitrary custom-node installation.

Model-download UX remains open. The initial product must explain missing models and provide a documented preparation path; do not silently download large models or assume redistribution rights.

## Engineering Decisions Still Open

Exact engine versions, reference models/providers, desktop wrapper, supported workflow import format, secure credential implementation, and minimum supported NVIDIA hardware. Resolve with documented evidence and small technical investigations. Escalate only decisions changing accepted scope, cost, privacy, or irreversible user-data behavior.
