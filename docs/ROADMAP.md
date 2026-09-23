# Berry AI Studio Implementation Roadmap

Date: 2026-09-23. This roadmap supersedes historical milestone completion claims.
No milestone below is marked accepted based on the existing prototype.

## M0 — Baseline and Implementation Decisions

- Read the approved vision/PRD, inspect current code and preserve local edits.
- Reproduce available tests/builds; record actual results and missing checks.
- Select reference engine versions, workflows, models and BYOK providers using official documentation.
- Document capability coverage for four image actions, packaging approach and platform boundaries.
- Break implementation into focused tasks/PRs targeting dev.

Exit: traceable implementation plan, current baseline, and documented reference integration matrix. Missing external access is explicit.

## M1 — Reliable Core and Persistent Projects

- Repair real output retrieval, missing preview handling, targeted execution, cache correctness and failure propagation.
- Add task/run identities, immutable submissions, truthful status, cancellation semantics and restart recovery.
- Persist projects/assets/history/cache with versioned schemas.
- Add semantic cache and DAG regression tests.

Exit: fixture-backed end-to-end task/persistence tests pass; no fake outputs or false completion; no claim of real integration acceptance yet.

## M2 — Engines and Model Readiness

- Add separate isolated installers and lifecycle adapters for ComfyUI and Stable Diffusion WebUI.
- Connect existing engines without unintended mutation or process ownership.
- Add hardware/storage readiness, model scanning/import/roots and compatibility/dependency guidance.
- Remove host-Python fallback; handle interrupted setup.

Exit: documented clean Windows and existing-installation smoke tests; library originals remain intact; engine failures are actionable.

## M3 — Primary Canvas and Image Creation

- Implement canvas import/placement/selection/contextual creation and durable layouts.
- Deliver text-to-image, image-to-image, mask-based inpainting and upscaling using curated mappings.
- Add native entry points, result provenance, history and export.
- Provide newcomer-friendly controls without required node wiring.

Exit: approved local image journey passes on a documented NVIDIA configuration; both engines perform real Berry-driven generation.

## M4 — Cloud-Only Creation

- Add provider selection, secure BYOK setup, capability discovery and reference image action coverage.
- Reuse projects, canvas, tasks, history and assets.
- Expose upload/execution location; use truthful cancellation and retry semantics.
- Verify startup and creation without torch/local engines.

Exit: real cloud-only image journey passes with explicitly authorized test credentials/spend; mocks alone do not satisfy this gate.

## M5 — Release Readiness

- Complete Windows packaging/onboarding and documented prerequisites.
- Run PRD release scenarios, failure recovery, secret redaction and asset/cache checks.
- Run portable core CI on Windows and a non-Windows OS; document unsupported release targets.
- Publish an English support matrix, known limitations, user setup guide and test evidence.

Exit: all in-scope requirements verified or explicitly returned to the product owner as release blockers. Do not silently defer approved scope.

## Later Roadmap

Video generation, richer templates, Agent-assisted existing workflows then automated workflow construction/repair, clarified CLI integration, non-NVIDIA discrete GPU inference, and additional OS distributions.

## Evidence Rules

Keep a requirement-to-test mapping for R01–R18. Each milestone report lists delivered behavior, tests executed, actual results, remaining risks and blockers. External hardware/API tests not run must be labeled unverified. Historical test counts and checked boxes are not current evidence.
