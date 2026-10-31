# Review follow-up: 2026-11-01

Status: review defects repaired and integrated into `dev`; first-release acceptance remains incomplete.

This report records development evidence, not a release approval. Historical VERIFIED labels in other reports do not replace the [current-head release gate](../RELEASE_ACCEPTANCE_GATE.md).

## Fixes

Each PR targets `dev` and preserves its small implementation/test commits. Branches were updated against the preceding merge and merged only after all required CI jobs passed; no checks were bypassed and no commits were squashed.

| Review finding | Integrated repair |
| --- | --- |
| F01/F02: project save loss and save/switch races | Existing store fixes were retained; [#230](https://github.com/BerryUIKI/AI-Studio/pull/230) keeps failed project actions recoverable and gates close/shutdown on a successful save. |
| Engine startup and health | [#231](https://github.com/BerryUIKI/AI-Studio/pull/231) distinguishes process ownership from observed service health, retains Starting, and reports failed stops. |
| F03/F07: wrong engine controls and native URLs | [#232](https://github.com/BerryUIKI/AI-Studio/pull/232) retains connection identity and complete HTTP(S) endpoints, starts the selected engine, and withholds external lifecycle controls. |
| F05: OpenAI-only default Cloud routing | [#233](https://github.com/BerryUIKI/AI-Studio/pull/233) supplies the configured provider/model fallback; no live provider compatibility is inferred. |
| F06: editing errors behind dialogs | [#234](https://github.com/BerryUIKI/AI-Studio/pull/234) displays task/error/cancellation feedback in Inpaint and Upscale and permits dialog scrolling. |
| F04/F08: external selection and Models shortcut | Existing registry-based selection was retained; [#235](https://github.com/BerryUIKI/AI-Studio/pull/235) verifies external selection and makes Models reopen on the inventory tab. |
| Seed zero | [#236](https://github.com/BerryUIKI/AI-Studio/pull/236) preserves zero and labels random/empty input. |
| Download test warnings | [#238](https://github.com/BerryUIKI/AI-Studio/pull/238) exercises the real async stream protocol with suitable mocks. |
| Packaging guard | [#239](https://github.com/BerryUIKI/AI-Studio/pull/239) validates Tauri v2 `frontendDist` and rejects missing/wrong paths or reversed build order instead of issuing a warning. |
| Tauri dependency mismatch | [#240](https://github.com/BerryUIKI/AI-Studio/pull/240) aligns both dialog plugins to 2.7.3 and adds a Tauri CLI packaging check to CI. |
| Async fixture scope warning | [#241](https://github.com/BerryUIKI/AI-Studio/pull/241) declares the pytest fixture event-loop scope, removing the remaining backend configuration warning. |

## Recorded validation

- Integration source: `4d72f0fcd3da032dfb400df92ae00054ab4eba1f`, the `dev` head after [#241](https://github.com/BerryUIKI/AI-Studio/pull/241) merged. Documentation added in this PR does not turn that baseline into release evidence.
- Host: Windows 11 Enterprise x64, build 26200; Python 3.12.14 in an isolated downloaded runtime; Node.js 20.18.0; pnpm 12.8.1; Rust 1.99.0. CI uses Python 3.12 and Node.js 24.
- Frontend: 263 tests across 49 files; lint, type-check and production build passed. The tested frontend commit is `db8e571df83f82d0e591d9efe9b239d0762bb6fd`; a tree comparison confirmed no subsequent change under `frontend/src/` or `frontend/src-tauri/src/`. Largest JS chunk: 481.88 kB (132.53 kB gzip).
- Backend: 541 tests passed (132.59s) on `faa002bf9802a04826d132f4feb00c0e552b5152`, the [#241](https://github.com/BerryUIKI/AI-Studio/pull/241) head. The only remaining warning came from third-party Starlette test-client code, not the project suite. [#241](https://github.com/BerryUIKI/AI-Studio/pull/241) adds the missing fixture event-loop scope configuration.
- Native Rust: 22 tests passed — 1 desktop library, 7 window-controls integration, 11 shared-runtime and 3 launcher. The 2 `setup_acceptance` integration tests stay ignored unless explicitly opted in, and both were run and passed separately: cancellation/concurrent-install exclusion/retry/read-only environment selection, and real backend readiness plus owned-process shutdown using the newly installed Python.
- Standalone runtime: pinned archive checksum, isolated imports, relocation, `venv` and `pip` passed without host Python on PATH. No global Python packages or GPU/model installations were added.
- Package: `Berry AI Studio_0.1.0_x64-setup.exe` (3.26 MiB NSIS bundle) and the portable archive `Berry-AI-Studio-v0.1.0-review.20261101-windows-x64.zip` (246,730,175 bytes) were built from `62673d5e0ea55806b08bb3bd0a56e208e4c4d070`. The Tauri CLI build compiled `tauri-plugin-dialog v2.7.3`, confirming the aligned pin.
- Package scope: the archive was extraction-smoke-tested from a relocated path and the smoke run was repeated on 2026-11-01 against the delivered ZIP. Both runs passed the bundled launcher, bundled Git, isolated backend imports and engine `venv` creation under a system-only PATH. This does not exercise desktop startup, image creation, GPU inference or installation, and it is not clean Windows VM evidence.
- Persistence host probe: imported fixture bytes, project name/layout and asset references survived a real backend restart; exported bytes matched. This ran against both the source tree and the built package. It does not exercise GUI project restoration or image inference.
- Release evidence source checks: 2 passed. Required PR CI includes backend, frontend, Rust and portable core on Windows/Ubuntu. Git diff whitespace checks passed.
- Requirement coverage and the per-requirement gaps are recorded in the acceptance matrix below.
- Raw logs, local package candidates and JSON check records remain outside Git under the managed review worktree's `.review-runtime/2026-11-01/`. The original checkout's pre-existing changes were preserved. Commits used a command-scoped signing override because the configured 1Password signing socket was unavailable; user/global configuration was unchanged.

## Remaining release acceptance

The following coverage is a development baseline. Only R17 has the portable CI evidence allowed by the release gate; the other rows still require their current-head live scenarios and artifacts.

| Requirements | Available evidence | Still unverified |
| --- | --- | --- |
| R01, R02, L02, L09 | Lightweight runtime imports, real readiness, hardware/readiness contract tests | Visual onboarding and actual supported device guidance |
| R03, R05, L05, L06 | Core setup cancellation/retry; engine ownership, health and failure regressions | Real ComfyUI/WebUI installation, startup failures and recovery |
| R04, R18 | External selection, retained identity/URL and no external lifecycle controls | Actual native entry points and desktop embedding/CSP behavior |
| R06 | Canvas/component regressions and production build | Pan/zoom, selection, keyboard/focus and layout at supported sizes/scales |
| R07–R10, R13, R14 | Creation/capability/routing/task tests and visible dialog failures | Real local and cloud text-to-image, image-to-image, inpaint, upscale, cancellation and export |
| R11, R12, L10 | Inventory/root safety and repeatable Models navigation regressions | Interactive model inventory on reference engines |
| R15, R16 | Save recovery, persistence/cache tests and host restart fixture | Packaged GUI restart with actual generated assets/history and cache reuse |
| R17 | Portable core CI passed on Windows and Ubuntu | Non-Windows release support is not claimed |
| L01 | Portable archive smoke passed from a relocated path and a system-only PATH | Clean Windows entry point and installation journey |
| L03, L07, L11 | Rust boundaries, startup/shutdown tests and actual owned backend stop | Duplicate native launch, port conflict UX and active-task window exit |
| L04 | Observed service-health and UI state regressions | Status presentation against real managed/external engines |
| L08, L12 | Update/active-task/rollback regression tests | Packaged app update and interrupted managed-engine update preserving user data |

GUI automation was rejected again when opening the local test page by the saved permission/managed policy, despite prior user authorization. No alternative GUI route was used. Live browser/desktop acceptance is therefore unverified.

Before promotion, run the PRD image journeys on documented NVIDIA ComfyUI and WebUI installations, a funded and explicitly authorized cloud configuration, and a clean Windows VM. Include 1024×700 and 1440×900 layouts at 125%/150% display scale, mask alignment, failure/retry, restart/history/export and update recovery. Record engine/model/provider versions and nonempty output/diagnostic files on the exact candidate SHA in an external evidence bundle, validate it with `scripts/verify-release-evidence.py`, and follow the release gate and product-owner approval policy. No release branch, `main` promotion, tag or publication was performed.
