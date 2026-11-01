<!-- berry-review:2026-10-05:tracker -->
## Purpose

Track the 2026-10-05 product and technical review of Berry AI Studio at [`c1c5dbe`](https://github.com/BerryUIKI/AI-Studio/commit/c1c5dbeaace01fc5e3fa68d8e3ebf410583b775b) on `dev`.

The review identified 44 findings: 19 proposed first-release blockers (P1) and 25 material improvements/validation tasks (P2). Individual issues distinguish reproduced observations, code findings, and unverified integration risks. Proposed priority does not imply a production incident.

## Review baseline

- Backend: 157 tests passed.
- Frontend: 41 tests passed across 9 files; production build passed; lint passed with 2 warnings.
- Launcher: 3 Rust tests passed; Tauri `cargo check --locked` passed.
- Browser: isolated first-use/navigation/configuration, canvas reload, import, and upscale-dialog checks.
- Disposable probes: credentials, ownership, provider/model dispatch, cache validity, installation state, model integrity, task history, and lifecycle guards.
- Additional packaging probe: copied venv still used a base runtime outside the staged directory.
- Real GPU inference, paid APIs, and clean-machine packaged acceptance were not verified.

There were no open issues at filing preflight. Related closed work is referenced in the relevant child issues; this review does not repeat already-fixed wildcard CORS or JSON-cloning claims. Existing repository labels are used, with no assignees or milestones imposed.

## Delivery sequence

1. Protect credentials, local control APIs, process ownership, uploaded media, and safe exit/update behavior.
2. Implement durable projects/tasks and one verified image workflow: model/provider identity, engine input/model paths, masks, dimensions, valid caching, and export.
3. Validate installation/download recovery, persist configuration, and prove clean-machine packaging.
4. Improve first-use UX, accessibility/localization, truthful diagnostics, performance, and maintainable typed contracts.

## Finding index

### P1: Proposed first-release blockers

- [ ] #101 — **F01**: Security: Protect stored credentials and make API secret fields write-only
- [ ] #102 — **F02**: Security: Enforce a session boundary for local control APIs and WebSockets
- [ ] #103 — **F03**: Bug: Verify engine process ownership before terminating a stored PID
- [ ] #104 — **F04**: Bug: Save and reopen the complete canvas as a durable project
- [ ] #105 — **F05**: Bug: Transfer source images and masks into ComfyUI before execution
- [ ] #106 — **F06**: Bug: Normalize painted inpainting masks for each provider
- [ ] #107 — **F07**: Bug: Connect downloaded and shared model directories to engine search paths
- [ ] #108 — **F08**: Bug: Correct managed WebUI launch flags and isolated Python compatibility
- [ ] #109 — **F09**: Bug: Apply the selected WebUI checkpoint and record the effective model
- [ ] #110 — **F10**: Bug: Use one provider resolution plan for dispatch, hashing, and provenance
- [ ] #111 — **F11**: Bug: Invalidate cached results whose output assets are missing
- [ ] #112 — **F12**: Bug: Validate engine installation completion and preserve live install state
- [ ] #113 — **F13**: Bug: Verify model download integrity before promoting an artifact
- [ ] #114 — **F14**: Bug: Protect active creative tasks during engine updates and restore full runtimes
- [ ] #115 — **F15**: Bug: Respect shutdown refusal, process ownership, and Keep Running
- [ ] #116 — **F16**: Bug: Resume workflow subscriptions without resubmitting execution on reconnect
- [ ] #117 — **F17**: Bug: Fail workflows with missing runners and validate execution contracts
- [ ] #118 — **F18**: Bug: Package a complete portable runtime and verify clean-machine startup
- [ ] #119 — **F19**: Security: Validate uploaded media and isolate active content from the app origin

### P2: Material improvements and validation

- [ ] #120 — **F20**: Enhancement: Persist task transitions and generation history across restart
- [ ] #121 — **F21**: Enhancement: Return task IDs at submission and expose accurate cancellation states
- [ ] #122 — **F22**: Refactor: Share a canonical execution and cache-validity contract with planning
- [ ] #123 — **F23**: Bug: Use actual image dimensions and honor the selected upscale factor
- [ ] #124 — **F24**: Bug: Restore complete canvas transactions with undo and redo
- [ ] #125 — **F25**: Bug: Persist engine configuration before showing a successful save
- [ ] #126 — **F26**: Bug: Make Uninstall and Open Folder perform their advertised actions
- [ ] #127 — **F27**: Bug: Resolve lifecycle and execution through the selected engine connection
- [ ] #128 — **F28**: Bug: Persist library and connection settings and apply selected mirrors
- [ ] #129 — **F29**: Bug: Preserve unknown model compatibility and validate readiness dependencies
- [ ] #130 — **F30**: Enhancement: Connect Model Hub discovery to installation, selection, and truthful estimates
- [ ] #131 — **F31**: Enhancement: Guide first-time users to a validated first image
- [ ] #132 — **F32**: Enhancement: Prioritize the verified image workflow in first-release navigation
- [ ] #133 — **F33**: Bug: Report observed progress, real engine logs, and service health
- [ ] #134 — **F34**: Bug: Preserve Agent conversation identity and place outputs in project context
- [ ] #135 — **F35**: Bug: Complete embedded LLM lifecycle results and readiness checks
- [ ] #136 — **F36**: Bug: Render and export managed media using verified MIME and format metadata
- [ ] #137 — **F37**: Enhancement: Improve canvas information hierarchy and resilient visual feedback
- [ ] #138 — **F38**: Enhancement: Standardize accessible dialogs and scope canvas keyboard shortcuts
- [ ] #139 — **F39**: Enhancement: Align advertised language support with complete workflow translations
- [ ] #140 — **F40**: Performance: Move blocking inventory and hardware work off async request paths
- [ ] #141 — **F41**: Performance: Limit store subscriptions, polling, and inactive-view effects
- [ ] #142 — **F42**: Refactor: Consolidate typed execution, lifecycle, and API contracts
- [ ] #143 — **F43**: Test: Gate release verification on current-head end-to-end acceptance
- [ ] #144 — **F44**: Validation: Verify native capabilities and CSP on the production backend origin

## Release acceptance

- [ ] A new user reaches a first cloud image without local engine/GPU dependencies.
- [ ] Complete project state and generation history survive restart.
- [ ] Supported real-engine txt2img, img2img, known-region inpainting, upscale, and export pass.
- [ ] Actual provider/model identity matches selection, cache identity, and provenance.
- [ ] Reconnect/cancellation/retry preserve durable truthful task state without duplicate inference.
- [ ] Interrupted installation/download/update recovers without damaging previous valid artifacts.
- [ ] No stop/update/exit path terminates an unowned process or bypasses an active-task refusal.
- [ ] Secrets and uploaded content cannot cross application security boundaries.
- [ ] A clean-machine packaged native production-origin journey passes.

Follow-up changes should use focused branches/PRs targeting `dev` under CONTRIBUTING.md. Completion should be supported by current-head evidence rather than test counts alone.
