# Berry AI Studio Product Vision

Date: 2026-09-23. Status: approved product direction.
Owner: product owner, supported by the CTO/product-management assistant.

## Purpose

Help beginners move from tool setup to finished AI artwork in one workspace. Berry provides its own creation interface, an infinite canvas, engine management, model management, and persistent projects.

The primary user wants to generate and edit images without learning environment setup or low-level workflow wiring. Existing ComfyUI and Stable Diffusion WebUI users can connect their installations and retain native UI access.

## Approved Product Decisions

- Windows is the initial release platform; design the code for multiple platforms from the beginning.
- Support NVIDIA local generation and cloud creation in the first release.
- Keep the application usable without GPU dependencies or local engines.
- Provide managed installation and connection to existing ComfyUI and Stable Diffusion WebUI installations. Users install only what they need.
- Make Berry's infinite canvas the primary workspace. Users place references and results, select an image, and launch a creative action without wiring nodes.
- Retain native engine entry points for advanced use.
- Include text-to-image, image-to-image, inpainting, and upscaling in the first release.
- Provide local model scanning, importing, directory management, compatibility information, and missing-dependency guidance.
- Provide a Rust-based launcher/environment manager that opens Berry, shows the unified model inventory, and manages installation, deployment, lifecycle and updates for Berry-managed ComfyUI and Stable Diffusion WebUI.
- Cloud creation initially uses user-provided API keys and provider selection.
- Save projects, assets, and generation records so work can resume after restart.
- Defer video creation and Agent features. Future Agents may use existing workflows and construct workflows automatically.
- Consider non-NVIDIA discrete GPU inference later. CPU, integrated GPU, and NPU support are not confirmed requirements.
- CLI-based generation remains a future direction; its exact meaning is unresolved.
- All project-facing written artifacts use English.

## First Successful User Journey

A user opens Berry, checks device readiness, installs or connects ComfyUI, prepares a compatible model, generates several images from a prompt, places a selected result on the canvas, masks a region and edits it, upscales it, and exports the result. Reopening the project restores the canvas, source assets, and generation history.

A cloud-only user completes an equivalent supported image workflow by configuring a provider and API key, without installing Python generation environments or local engines.

## Product Boundaries

Berry owns the primary creation experience and task/asset records. Engines perform inference. Native engine editors remain accessible, but bidirectional synchronization of arbitrary native edits is not promised.

An infinite canvas is a creative workspace, not a requirement to expose engine internals. Any visible execution ports remain limited to string, image, audio, video, and json.

Long-term breadth must not prevent the first image workflow from being reliable. No video editor, marketplace, platform billing service, team collaboration, or autonomous Agent system is included in the first release.

## Success Measures

Acceptance is based on the scenarios in [PRD](PRD.md), with recorded evidence rather than historical completion labels. Record onboarding time, time to first successful image, failure/recovery outcomes, and project restoration success on a documented test machine. Numerical performance targets require measured baselines; do not invent speed or package-size guarantees.
