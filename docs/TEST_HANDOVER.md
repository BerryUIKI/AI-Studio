# Berry AI Studio current-head testing handover

Prepared 2026-10-13. Published to GitHub for the requested device handoff. The actual acceptance evidence remains external to Git.

Implementation PRs #186–#192 are merged into dev. The resource-contract follow-up is on `bugfix/142-resource-contracts`; check its PR and CI before merging. Source baseline before the handoff documentation: `1213bf92bd52b8665c3183dc26a75079541687ca`. Fetch the latest branch/dev SHA before testing; acceptance must match that exact candidate. All 20 issue acceptance records remain open.


## Authority and evidence boundaries

The implementation agent may run automated fixture regressions and builds. The user explicitly assigned live local/cloud inference, performance profiling and clean Windows acceptance to a separate testing agent because this device cannot perform the local engine tests. No paid API budget was authorized for this run and no paid requests were made. Obtain the testing owner's approved provider accounts and spending limit before paid execution; never include keys in artifacts. Do not promote, tag or publish to main.

Fetch dev and record its full SHA before testing. Never transfer a passing observation to a different commit without rerunning the affected journey. Implementation PRs: #186 (durable submissions/Agent context), #187 (first image UI/accessibility), #188 (task races/shared native runtime), #189 (remaining accessible dialogs), #190 (release acceptance workflow), #191 (typed services/download contracts/truthful progress), #192 (locale catalog and formatting). The follow-up verifies injected cache ownership and configured native endpoints. See CONTINUATION_CONTEXT.md for status and CI links.

## Available automated evidence

On the previous Windows device: Python 3.12, Node 24.14.1 and pnpm 11.18.0. The final synchronized frontend source passes 160 tests, typecheck and lint (two existing empty-block warnings). The full backend had 389 passing tests before the final cache-ownership change; all 18 affected backend tests pass afterward. Shared runtime and launcher tests passed 4 + 3. Frontend production build and native frontend cargo check passed earlier; use latest CI for the final candidate. Backend fixture warnings include SQLite workers reaching closed test loops, Starlette deprecations and mocked LLM stream warnings. These are not live acceptance claims.

Backend regressions cover masks, content identity, cache validity, restart reconciliation, cancel races, project/task/conversation persistence, dimensions, media metadata, engine ownership and worker responsiveness. Rendered frontend regressions cover dialogs/focus, disabled unready generation, explicit provider choices, conversation continuity, inactive-view unmounting and shortcut contexts. Run the full suites again on the exact candidate. CI's Portable Core matrix covers Windows and Ubuntu; Ubuntu CI is not non-Windows product release support.

Browser layout was inspected at 1024x700, 1366x768 and CSS equivalents 819x560 and 683x467. These last two are useful responsive checks, not evidence of native Windows DPI scaling. No creation request was sent. The local browser screenshot is not included in Git; capture fresh final-head evidence on the test device. Main production JavaScript after lazy secondary views: 641.11 kB / 188.55 kB gzip; before lazy splitting in this working session: 703.34 kB / 201.77 kB gzip. The locale catalog build later measured 683.49 kB / 200.94 kB gzip. These are historical bundle-size observations, not startup or frame-time improvements; profile the final candidate.

## Issue-to-acceptance matrix

Every issue below remains open pending criterion-by-criterion evidence. Existing fixes on remote dev were retained rather than reimplemented. Consult each linked GitHub issue for its current acceptance checklist. Recheck the open issue list before closure.

| Issue | Implementation/regression evidence | Required acceptance before closure |
| --- | --- | --- |
| [#106](https://github.com/BerryUIKI/AI-Studio/issues/106) | mask_converter + mask_adapter_payloads; provider-specific edit/protect conversions | S04: known painted region on real ComfyUI, WebUI and supported cloud adapter; dimension/coordinate alignment |
| [#118](https://github.com/BerryUIKI/AI-Studio/issues/118) | pinned standalone runtime/package scripts; source-only PATH fallback; CI relocation | S11: clean Windows package without Python/Git/Node; launch, prerequisites, cloud image and safe exit |
| [#120](https://github.com/BerryUIKI/AI-Studio/issues/120) | immutable run submissions, task transitions/events, restart reconciliation; task_store/events/history tests | S06/S07: restart between remote submission and result, retained errors/outputs, no uncertain paid resubmit |
| [#121](https://github.com/BerryUIKI/AI-Studio/issues/121) | 202 task identity, SSE/status retrieval, bounded shared scheduler, truthful cancellation; submissions/cancellation tests | S02/S06: immediate identity, queued/running cancel races, unsupported remote cancellation disclosure, explicit retry |
| [#122](https://github.com/BerryUIKI/AI-Studio/issues/122) | workflow_spec/creative_identity shared effective spec; DAG/content cache tests | S07: planning/dispatch/hash/provenance agreement; bindings/content/model/runtime changes invalidate; missing output cannot hit |
| [#124](https://github.com/BerryUIKI/AI-Studio/issues/124) | complete canvas transactions and grouped result insertion; canvas store regressions | S03: undo/redo create/import/move/connect/delete/clear/grouped outputs restores relationships and selection after reopen |
| [#130](https://github.com/BerryUIKI/AI-Studio/issues/130) | inventory reconciliation, action model catalog, install-to-readiness refresh, available-VRAM assumptions | S01/S08: discovery→install→index→readiness→selection; unknown remains unknown; observed estimates vs assumptions |
| [#131](https://github.com/BerryUIKI/AI-Studio/issues/131) | default canvas, cloud/local repair links, readiness gate, explicit model/location | S01/S02: new user reaches cloud and each local first image; retry missing model/invalid key/disconnected engine |
| [#132](https://github.com/BerryUIKI/AI-Studio/issues/132) | primary canvas/model/setup navigation, experimental/native controls secondary | S01/S03: complete project→create/import→select/edit→export without node wiring; secondary features still accessible |
| [#133](https://github.com/BerryUIKI/AI-Studio/issues/133) | observed task progress, bounded redacted process diagnostics, exact service health | S02/S09: no invented percentages, real logs and readiness, redaction, missing/degraded service states |
| [#134](https://github.com/BerryUIKI/AI-Studio/issues/134) | durable project-linked bounded Agent history, shared accepted-proposal tasks, nearby placement | S05: remount/restart/follow-up continuity, project switches, multi-result placement and one undo transaction |
| [#136](https://github.com/BerryUIKI/AI-Studio/issues/136) | verified MIME/extensions/animation/codec metadata, frontend media rendering/export; media_metadata tests | S03: JPEG/WebP/GIF/MP4 import/display/export byte and metadata checks, misleading names rejected |
| [#137](https://github.com/BerryUIKI/AI-Studio/issues/137) | resilient thumbnails, compact creation controls, secondary hierarchy, accessible fallback text | S01/S10: minimal window/laptop/DPI, missing thumbnails, long errors, mixed large canvas and task progress readability |
| [#138](https://github.com/BerryUIKI/AI-Studio/issues/138) | shared focus-trapping dialogs, restoration/Escape, active-view shortcut guards; renderedJourney tests | S10: all migrated dialogs keyboard-only/screen-reader; nested dialogs; editable contexts never trigger canvas deletion |
| [#139](https://github.com/BerryUIKI/AI-Studio/issues/139) | only English primary workflow advertised verified; other translations marked previews; shared formatting helpers | S10: complete English workflow; preview language coverage/fallbacks; inspect remaining strings/formatting, do not certify preview locales |
| [#140](https://github.com/BerryUIKI/AI-Studio/issues/140) | bounded workers, incremental inventory, cached hardware/status; backend_responsiveness tests | S12: comparative p50/p95/max health/task latency during real large scans/imports/hash/probes; routine polling never rescans |
| [#141](https://github.com/BerryUIKI/AI-Studio/issues/141) | focused subscriptions/shared engine polling/lazy secondary views/inactive unmount; rendered tests | S12: large-canvas render counts, frame times, idle request/effect counts and startup before/after on same hardware |
| [#142](https://github.com/BerryUIKI/AI-Studio/issues/142) | typed execution/services/task/asset contracts, creative thin router, shared Rust supervisor, targeted lint | S02/S09 + source audit: identity/contracts match bundled clients; review the extracted workflow/asset/task/engine services, documented typing/geometry exceptions and injected cache ownership; refactors preserve behavior |
| [#143](https://github.com/BerryUIKI/AI-Studio/issues/143) | current-head evidence CLI, historical report disclaimer, rendered tests + portable CI | All S01–S12 + R01–R18/L01–L12 records; clean packaged journey; validator succeeds only with actual artifacts |
| [#100](https://github.com/BerryUIKI/AI-Studio/issues/100) | tracker only | Close last, after child criteria and complete current-head acceptance; do not infer completion from test counts |

## Test fixtures and environment manifest

Use dedicated disposable projects and isolated app data. Retain an untouched copy of an existing project/database before migration tests. Record OS/build, CPU/RAM/GPU/driver and available VRAM, display/window/DPI, disk type/free space, app commit/package SHA256, runtime Python, engine version/commit/extensions/template checksum, provider endpoint/API version, model exact ID/revision/file SHA256 and seed/parameters. Capture timestamps, task/run/event/remote IDs, effective execution specification and output IDs/hashes/MIME. Logs and screenshots must redact secrets. Keep original output files, not only screenshots.

Create a 1024x768 asymmetric image with colored corners, grid and a distinct centered object. Make both a small center mask and an off-center mask touching one edge, with transparent unpainted pixels and white opaque paint. Include portrait/landscape/odd-sized source variants. Include real JPEG, WebP, animated GIF and short MP4 with known pixel dimensions/frame count/codec; include an invalid/truncated media sample. Prepare one valid SD1.5 or SDXL checkpoint and the supported template dependencies for each local engine. Unknown/unsupported/truncated models must not become ready. Do not use random files as inference models.

## S01 — Onboarding and model discovery

1. In new isolated data, launch with no local engines and no torch in the core environment. Canvas is primary; cloud setup offers supported actions and upload disclosure. Missing hardware does not prevent cloud mode.
2. Configure an approved provider through the UI. Invalid key produces useful failure; the key is absent from browser persistence, export and logs. Enter valid key only through owner's approved secret process.
3. Discover a local supported model, install to chosen root, watch observed progress, inspect integrity/dependencies/readiness, select Use. Selection must use actual installed filename and correct engine. Refresh after install must avoid requiring app restart.
4. Repeat with unknown and missing-dependency models; neither may be advertised verified. Available VRAM estimates say their assumptions and do not claim measured latency. Confirm no global Python package installation.
5. Run setup repair with engine stopped, invalid port, missing model and download interrupted. Previously valid artifacts and source files survive. Record every supported vs unsupported combination.

## S02 — Cloud/local first image and truthful task lifecycle

For approved cloud provider, managed ComfyUI and managed WebUI separately:
1. New project, explicit provider/connection/model, prompt and supported controls; submit. The response returns durable task/run ID immediately (202), before inference completion. SSE/status updates use that ID; losing subscription never triggers another POST.
2. Verify queued/running/succeeded state and observed progress (indeterminate if provider lacks progress). Canvas result exists only after an accessible adopted asset. Compare selected, dispatch and effective provider/model/engine identity against output provenance.
3. Submit enough controlled tasks to exercise two workers and bounded queue. Queued cancellation prevents dispatch. Race running cancellation with task state save and output completion; no stale write hides cancellation. Unsupported remote cancellation explains continuing compute/possible charges.
4. Failed request retains diagnostic/error history. Retry is an explicit new task. Uncertain remote retry warns about duplicate charges and requires explicit user action.
5. Experimental video is secondary. Validate only provider/engine combinations explicitly supported; record unsupported combinations as such rather than silently changing models.

## S03 — Canvas, project persistence and verified media

1. Import each media fixture; verify renderer (image/animation/video), natural dimensions, MIME/extension and accessible thumbnail fallback. Select/edit/remove on canvas without deleting original source files. Export and compare signatures, MIME, file extension, codec/animation and hashes where bytes are retained.
2. Create/import/move/group/connect/delete/clear, undo then redo each; relationships and selection restore with objects. No manual connections required for primary image workflow.
3. Save project, restart entire app/backend, reopen. Positions, zoom where supported, relationships, selection policy, asset links and generation history survive. Missing original external file has useful feedback; generated assets remain available after remote URL expires.
4. Upscale a selected image 2x/4x where supported, compare actual output dimensions and displayed/exported dimensions. Preserve source beside result. Do not call inaccessible output success.

## S04 — Known-region inpainting

1. Open source from S03; paint center and off-center masks, preview source/mask alignment and submit the supported provider-specific edit path.
2. Canonical paint means edit. Preserve unpainted area within documented engine tolerances; save source, canonical mask, converted mask and generated output. Calculate/visualize regional difference and report tolerated boundary effects, not just subjective appearance.
3. Repeat non-square and resized source; colored corner/grid locations expose flips/stretch/crop. Inspect converted ComfyUI alpha, WebUI grayscale and supported cloud convention independently. Disabled unsupported OpenAI edit is not a claimed passing edit adapter.

## S05 — Agent continuity and placement

1. In project A, send message then follow-up; verify same durable conversation ID and context. Close/reopen Agent panel and restart backend/app, then follow-up. Transcript restores without overwriting newer responses.
2. Switch to B while A response is pending. A output/history remain in A; B conversation is separate. Invalid cross-project conversation ID is rejected.
3. Accept proposal with multiple steps; inspect shared task identity/status/history, failure stops chain, successful media placed near source without overlap. One undo restores the full pre-proposal canvas. Confirm retention bounds and no credential fields in persisted transcript.

## S06 — Restart reconciliation and cancellation

1. Exercise queued/running/cancel-requested/failed/succeeded persisted states across orderly restart and abrupt backend exit in a disposable environment.
2. For a provider with remote job IDs, terminate after job acknowledgement before output download. Restart must retain ID and reconcile by lookup when supported; no automatic paid resubmission. If outcome cannot be known, history must report uncertain/interrupted state and preserve original immutable submission.
3. Reconnect after several SSE events with after_sequence; events are ordered/durable and status fallback refers to same task. Repeat cancellation before dispatch, during submission acknowledgement, while polling and after success.

## S07 — Canonical cache agreement

1. Fixed seed/model/runtime/source/port bindings: execute, then unchanged execute. Check plan says cacheable/cached consistently with execution and no new provider request. Reopen/restart and repeat.
2. Independently change prompt, seed, relevant params, source bytes at same path, mask content, port bindings, model bytes under same filename, model revision and effective runtime/provider identity. Each relevant change invalidates reuse. Layout-only changes do not request inference.
3. Delete/restrict access to cached managed output, corrupt bytes, remove asset binding. No false cache hit. Name-only unverified local model identity cannot establish a persistent workflow cache hit.
4. Generate again/New variation changes seed or explicitly busts cache. Record exact specification/hash and accessible output content hashes for each case.

## S08 — Installation, libraries and update recovery

1. Independently install managed ComfyUI/WebUI to isolated destinations, verify prerequisites and completion. Interrupt download/extract/setup then retry; incomplete state never ready. File hashes/architecture/dependencies checked before promotion.
2. Add/remove roots, import by reference/copy, rescan; no duplicate copies where sharing supported; removing index root does not remove source files. Repeated status polling uses inventory snapshot.
3. Managed engine update refuses active task; failed/interrupted update restores the recorded full runtime and retains models/config/projects/credentials. App update is separate. External install is neither silently upgraded nor deleted.

## S09 — Ownership, diagnostics and safe exit

1. Register existing external engine on nondefault port; verify exact identity/service readiness and correct native UI. A random HTTP server on that port cannot pass Berry health. Native edits do not imply synchronization.
2. Managed start/stop captures actual bounded logs, with redaction; PID alone cannot mean ready. Distinguish installed/stopped/starting/degraded/failed/unavailable.
3. Launch second Berry instance; no duplicate backend. Keep Running preserves tasks. Exit with active task produces refusal/choice; no hidden forced kill. StopOwned cannot terminate external engine/backend, reused PID or unknown process. Document owned processes before and after.
4. Check both Rust CLI and native desktop entry points follow the same ownership/health/shutdown contract. Packaged runtime absence fails visibly rather than using host Python. Developer setup now requires its documented venv; launcher no longer silently bootstraps one.

## S10 — Accessibility, layouts and locale coverage

1. Keyboard-only complete primary journey in English; all controls have names and focus indicators, model selection actionable, dialog labels associated. Tab/Shift+Tab stay within topmost dialog; Escape closes that dialog; focus returns to opener.
2. Test Agent, cloud, project, engine/config/add/setup, environment, inpaint/upscale/video dialogs, including nested dialogs. Delete/undo/redo inside input/textarea/contenteditable/select/buttons/dialogs do not modify hidden canvas. Inactive canvas has no global shortcuts.
3. Native minimum 1024x700 plus 1366x768 and 1920x1080; Windows 100%,125%,150% DPI, touchpad and keyboard. Confirm dock/history/dialog scroll, no clipped creation/close/export controls and no horizontal overflow; long provider/model names/errors and missing thumbnails remain readable.
4. English is the only currently advertised verified primary locale. Other retained languages are translation previews with English fallback. Audit every English journey and preview disclosures; record missing translations and consistent dates/numbers/errors. Do not claim full translation-system consolidation or certified preview locales from fallback alone.

## S11 — Clean Windows packaged journey

Build exact candidate package on host using scripts/package-windows-release.ps1, validate build order and package smoke test, record archive SHA256. Transfer to clean supported x64 Windows VM with no Python/Git/Node/dev tools. Follow docs/CLEAN_MACHINE_TESTING.md and actual current script parameters (do not reuse historical version claims).

Extract to a path with spaces and a non-ASCII user path. Start packaged executable from a different working directory. Frontend is embedded/current and production backend origin works with CSP/session boundary; WebView prerequisite handled. Controlled portable Python base/runtime stays inside package; no source-machine venv paths or PATH Python. Git prerequisite provisioning for managed installation is available as designed. Complete cloud onboarding/image/import/mask/upscale/export/project reopen and safe exit, then optional managed local installation on GPU VM. Include missing/corrupt runtime/frontend negative cases. This validates closed #144 and security/ownership regressions as affected, without reopening unrelated scope automatically.

## S12 — Comparative responsiveness

Use same machine/dataset/settings for remote baseline 0a9aef7 and final dev candidate. Record warm/cold separately, at least five runs, raw samples and median/p95/max. Profile real library sizes (1k/10k model references including large files) during cold scan, incremental scan, content hash/import and hardware probes. Concurrently sample health and task lookup every 100ms; measure event-loop lag, worker concurrency, CPU and memory. Routine manager polling must not trigger scans.

Create representative 100/500/1000 object canvases with mixed thumbnails/relationships and simulated task events. Measure pan/zoom/selection/undo frame time, unrelated component render counts, idle polling and inactive view listeners. Measure initial usable canvas time and secondary-view first-open time separately. Compare changed measures, report regressions and confidence; bundle reduction alone does not demonstrate startup improvement. No paid inference needed for this profiling.

## PRD and launcher mapping

| Requirement | Specific scenarios | Acceptance evidence |
| --- | --- | --- |
| R01 | S01, S02, S11 | live cloud-only startup plus packaged screenshot/output |
| R02 | S01, S10 | hardware/prerequisite observations, cloud works on unsupported GPU |
| R03 | S08, S11 | managed installation and interrupted recovery artifacts |
| R04 | S09 | existing engine identity/ownership/native entry observations |
| R05 | S09 | service health and bounded real diagnostic logs |
| R06 | S03, S10 | rendered canvas journey without wiring |
| R07 | S02 | real txt2img/img2img outputs/effective identity |
| R08 | S04 | canonical/converted mask and region-aligned live output |
| R09 | S03 | upscale dimensions and exported accessible file |
| R10 | S02, S08 | template/dependency preflight plus actual outputs |
| R11 | S01, S08 | inventory/file identities/unknown compatibility |
| R12 | S08 | root changes and retained source files |
| R13 | S01, S02, S11 | approved BYOK live output, upload disclosure/redaction |
| R14 | S02, S06 | task/event journal, cancel/retry/recovery observations |
| R15 | S03, S05, S06 | reopened project/assets/history/conversation |
| R16 | S07 | cache/no-dispatch and content/model invalidation evidence |
| R17 | S12 + portable CI | current commit Windows/Ubuntu core CI artifacts |
| R18 | S09 | native URL for each configured engine |
| L01 | S11 | packaged-live clean-machine journey |
| L02 | S11, S09 | observed startup/readiness and missing frontend error |
| L03 | S09 | duplicate launch and occupied non-Berry port |
| L04 | S01, S09 | distinct core/engine/cloud/model status |
| L05 | S08, S09 | independent managed lifecycle, preserved external processes |
| L06 | S01, S06, S08 | safe actionable recovery and redacted logs |
| L07 | S09 | Keep Running/refusal/exit ownership evidence |
| L08 | S08 | separate app/engine update behavior/version/recovery |
| L09 | S11 + portable CI | lightweight controlled runtime and OS adapters |
| L10 | S01, S08 | same backend catalog, unknowns/roots/retained originals |
| L11 | S09 + source/contracts | shared Rust supervision and local protocol behavior |
| L12 | S08, S11 | packaged-live active-task/interrupted update recovery |

## Reporting and issue closure

Use acceptance/evidence-template.json alongside this handover. It deliberately contains unverified records and must fail the gate until actual results and artifact paths are supplied. Required scenario IDs map as follows: cloud-image-journey=S02 cloud; comfyui-image-journey=S02 Comfy; webui-image-journey=S02 WebUI; project-reopen=S03; masked-edit=S04; upscale-export=S03; task-recovery=S06; external-ownership=S09; install-update-recovery=S08; safe-exit=S09; clean-windows-package=S11.

Run `python scripts/verify-release-evidence.py --evidence <path>/evidence.json --commit <full-tested-SHA>`. Each record needs status passed, evidence_level live/packaged-live (R17 permits ci) and actual nonempty relative artifacts within the evidence directory. L01/L12/clean-windows-package require packaged-live. The gate checks completeness/provenance metadata/files, not the truth of artifact contents; a reviewer must inspect them against the acceptance assertions. Release PRs to main must reference a successful same-repository exact-head evidence artifact as documented in RELEASE_ACCEPTANCE_GATE.md. Main branch protection now requires Current-head Release Acceptance in addition to its existing checks, with explicit owner approval.

Comment on each issue with exact tested SHA, criterion/result, scenario, environment/integration/model versions, output links and limitations. Close only after all its acceptance boxes are supported. Leave failures/unavailable tests open with precise blocker; file focused defects where appropriate. Recheck all open issues and close #100 last. No release/main promotion is authorized by this handover.
