# Device continuation context — 2026-10-13

## Latest continuation pass

PR #193 was rechecked at `def6e701188461205911952eb4191c7c768edafb`:
all five CI jobs passed, including the three required checks. It was merged with
a merge commit into `dev` at `3ad1641292461559a9accd5d5a3d1ba34be81867`.
PRs #194–#199 were then merged with merge commits after their required checks
passed. Integration baseline before this documentation update:
`2ca49aad7d5166e5023516c50511dd3291d21abe`. Fetch again before further work.

- #194: reproducible real HTTP scan/import responsiveness profiler for #140.
- #195: verify and atomically repair corrupt owned content on retry for S07.
- #196: trust the exact configured loopback origin; custom-port startup had
  rejected its own JavaScript with HTTP 403.
- #197: localized accessible names for project search/create/rename controls.
- #198: selection actions in the creation dock; Fit View had placed scaled card
  actions beneath the dock, intercepting pointer clicks.
- #199: preserve edits during active saves and await durable completion before
  project switches. A restored object had disappeared after restart.

The primary checkout's existing engine-store edit and untracked review directories
were preserved. Work and ignored evidence are in the attached `acceptance-100`
managed worktree. Keep its `.cache/acceptance` and `backend/.cache/acceptance`
directories when retaining device-local evidence; Git snapshots do not retain
ignored artifacts. Do not archive this worktree without preserving those files.

Available device: Windows 11 Enterprise build 26200, i5-12600KF, 32 GiB RAM,
RTX 4060 Ti with 16380 MiB reported VRAM / driver 616.92. The repository core
venv uses Python 3.14.5 without torch; frontend checks use Node 24.19.0 and
pnpm 12.8.1. The existing isolated ComfyUI checkout is
`f1072eb0350638a3390ddb6afbcaa8c6b237c6fd`, with torch `2.14.1+cpu`, no CUDA,
and no reference checkpoint. No working WebUI or clean Windows VM was exposed.
Native DPI and screen-reader acceptance were not performed.

The user explicitly chose **no paid testing**. Keep cloud acceptance blocked;
do not use existing credentials or submit paid requests. No release/main action
was performed. Main protection was read back with strict checks and the required
`Current-head Release Acceptance`; the unverified evidence template still fails.

Exact observations: 389 baseline backend tests at `3ad1641`; 400 backend tests
at `8b50948`; 168 frontend tests/build/typecheck at `9e739e0`. Lint retains two
existing warnings. PR #199 CI passed on exact head
`9e739e0d968247f79df0e2b539ed9ddbc71f12bd`:
https://github.com/BerryUIKI/AI-Studio/actions/runs/38409046432.
Real browser/HTTP checks covered source startup, readiness refusal, project
creation, JPEG/WebP/GIF/MP4 rendering/export hashes, project dialog keyboard
behavior, pointer deletion/undo, and an imported image surviving backend restart.
Browser viewport was 1024x700 CSS pixels, not native DPI evidence.

Criterion-specific observations are on issues #118, #122, #124, #136, #137,
#138 and #140. All 20 acceptance issues remain open. MP4 codec/backend dimensions
remain unknown despite browser decoding; live provider input compatibility remains
unverified. S12 has five runs per 1k/10k dataset against `0a9aef7` and `3ad1641`,
including real file hashing/imports and concurrent health/task latency. It still
needs CPU/memory/event-loop/worker telemetry, confidence analysis, and large-canvas
render/frame/idle profiling. No speed improvement or full S12 acceptance is claimed.
Continue those independent checks and the remaining S03/S07/S10 journeys; perform
GPU, packaged, native and cloud journeys only in a suitable authorized environment.
Close #100 last after every child criterion and current-head acceptance is supported.

## Historical handoff record

The sections below describe the previous device, before the continuation above.

## Objective and authority

Resolve the open implementation/validation issues and tracker #100 in
BerryUIKI/AI-Studio. Work from current `dev`, preserve earlier fixes, use focused
repository-policy branches and English Conventional Commits, merge only green
required checks, and close issues only with acceptance evidence. No release
promotion, tag or publication to `main` is authorized.

The user assigned live ComfyUI/WebUI, paid-provider, native DPI, clean Windows
and comparative performance acceptance to a separate testing agent. This device
cannot perform the local inference tests. No paid API requests were made and no
spending limit was authorized here. See [test specifications](TEST_HANDOVER.md)
and the deliberately unverified [evidence template](acceptance/evidence-template.json).
The latest instruction requested pushing everything and continuing on another
device, so these continuation documents are now Git-tracked.

## Delivered work

Merged into `dev`: PRs [#186](https://github.com/BerryUIKI/AI-Studio/pull/186),
[#187](https://github.com/BerryUIKI/AI-Studio/pull/187),
[#188](https://github.com/BerryUIKI/AI-Studio/pull/188),
[#189](https://github.com/BerryUIKI/AI-Studio/pull/189),
[#190](https://github.com/BerryUIKI/AI-Studio/pull/190),
[#191](https://github.com/BerryUIKI/AI-Studio/pull/191), and
[#192](https://github.com/BerryUIKI/AI-Studio/pull/192).

- Durable creative submission/status/events, immutable history, bounded scheduling,
  truthful cancellation, restart journaling and project-linked Agent conversations.
- First-image provider/model readiness, primary canvas navigation, accessible shared
  dialogs, focused subscriptions and suspended/lazy secondary views.
- Shared Rust backend supervision, packaged runtime restrictions and portable CI.
- Typed workflow/task/asset/engine services, one cancellation route/decision tree,
  validated download envelopes and observed installation progress.
- Typed locale catalog, English fallback, preview coverage disclosure, shared date
  and number formatting, and static checks for typing, styling and display strings.
- Release PR acceptance workflow and external exact-head evidence validation.

The user explicitly approved adding `Current-head Release Acceptance` to `main`'s
required checks. This was applied and read back successfully, preserving strictness
and the existing Backend Tests, Frontend Build & Typecheck, and Rust Launcher Build
& Test checks. Do not bypass this gate. No `main` code changes or release occurred.

## Where to resume

The remaining follow-up branch is `bugfix/142-resource-contracts`, based on current
`dev` and synchronized with PR #192. It contains two small verified source commits:
`35e14bd` routes workflow lookup/invalidation through the service-owned cache;
`cd6e41f` makes the titlebar native link follow the configured/reported endpoint.
Source baseline before handoff-only documentation: `1213bf92bd52b8665c3183dc26a75079541687ca`.
The latest merged `dev` at handoff preparation was
`bc1e739be33fee54b7ea5218af23d867fd6e2e7b`. Fetch again; these are historical anchors.

Check the open PR for that branch and its latest exact head. If CI is pending,
wait for all required checks. If green, merge using a merge commit to preserve
the focused commits, then update local `dev`. Do not assume a pushed branch is
merged. Recheck the open issue list before closing anything.

All 20 acceptance issues were still open at handoff: #100, #106, #118, #120,
#121, #122, #124, #130, #131, #132, #133, #134, #136, #137, #138, #139,
#140, #141, #142, #143. The handover maps each acceptance criterion and all
R01–R18/L01–L12 requirements to scenarios. #100 closes last.

## Evidence and environment

Final synchronized frontend source: **160 tests pass**, TypeScript passes, lint
has zero errors and two existing empty-block warnings. Before the final two
resource fixes, the full backend had **389 passing tests**; the final cache change
passes **18 affected backend regressions**. Native endpoint/routing tests pass
**15 affected frontend regressions**. Shared Rust/runtime tests: 4 + 3 pass.
Production frontend build and native frontend cargo check passed earlier; latest
CI should confirm the final candidate. These counts are fixture/build evidence.

PR #191 CI: https://github.com/BerryUIKI/AI-Studio/actions/runs/38370864068
PR #192 final CI: https://github.com/BerryUIKI/AI-Studio/actions/runs/38377122940
Both passed all five checks, including portable core on Windows and Ubuntu.

Runtime on the previous device: Python 3.12, Node 24.14.1, pnpm 11.18.0.
Use a repository venv; never install engine packages globally. Isolate test data
with BERRY_DATA_DIR and AI_WORKFLOW_ENGINE_DIR inside disposable repo directories.
Known fixture warnings: closed test-loop SQLite callbacks, Starlette deprecations
and mocked LLM stream warnings. Build retains a large-bundle warning. These do not
establish live integration or performance acceptance.

Read AGENTS.md and the product baseline documents before implementation. Also read
[service boundaries](SERVICE_BOUNDARIES.md), [creative API](CREATIVE_TASK_API.md),
[locale coverage](UI_LOCALE_COVERAGE.md) and [release gate](RELEASE_ACCEPTANCE_GATE.md).
The previous device's 1Password Git signer was unavailable; commits used a
per-command unsigned override, without changing persistent Git configuration.
Ignored caches, venvs, runtime data, build outputs and local browser screenshots
are not needed on the other device and are intentionally excluded from Git.
