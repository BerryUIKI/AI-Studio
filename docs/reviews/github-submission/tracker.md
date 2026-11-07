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

Individual issues will be linked here after submission and verified as sub-issues of this tracker.

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
