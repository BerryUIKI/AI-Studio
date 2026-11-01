# GitHub Submission Index: 2026-10-05 Review

Tracker: [[Tracking] First-release stabilization: 2026-10-05 product and technical review](https://github.com/BerryUIKI/AI-Studio/issues/100)

All 44 findings are submitted as native sub-issues. Evidence levels and priority recommendations remain explicit. Existing labels were used; no assignees or milestones were imposed.

| Finding | Priority | Evidence | GitHub issue |
| --- | --- | --- | --- |
| F01 | P1 | Reproduced | [#101: Security: Protect stored credentials and make API secret fields write-only](https://github.com/BerryUIKI/AI-Studio/issues/101) |
| F02 | P1 | Reproduced + Code | [#102: Security: Enforce a session boundary for local control APIs and WebSockets](https://github.com/BerryUIKI/AI-Studio/issues/102) |
| F03 | P1 | Reproduced | [#103: Bug: Verify engine process ownership before terminating a stored PID](https://github.com/BerryUIKI/AI-Studio/issues/103) |
| F04 | P1 | Reproduced + Code | [#104: Bug: Save and reopen the complete canvas as a durable project](https://github.com/BerryUIKI/AI-Studio/issues/104) |
| F05 | P1 | Code | [#105: Bug: Transfer source images and masks into ComfyUI before execution](https://github.com/BerryUIKI/AI-Studio/issues/105) |
| F06 | P1 | Code, checked against upstream semantics | [#106: Bug: Normalize painted inpainting masks for each provider](https://github.com/BerryUIKI/AI-Studio/issues/106) |
| F07 | P1 | Code | [#107: Bug: Connect downloaded and shared model directories to engine search paths](https://github.com/BerryUIKI/AI-Studio/issues/107) |
| F08 | P1 | Code | [#108: Bug: Correct managed WebUI launch flags and isolated Python compatibility](https://github.com/BerryUIKI/AI-Studio/issues/108) |
| F09 | P1 | Reproduced | [#109: Bug: Apply the selected WebUI checkpoint and record the effective model](https://github.com/BerryUIKI/AI-Studio/issues/109) |
| F10 | P1 | Reproduced | [#110: Bug: Use one provider resolution plan for dispatch, hashing, and provenance](https://github.com/BerryUIKI/AI-Studio/issues/110) |
| F11 | P1 | Reproduced | [#111: Bug: Invalidate cached results whose output assets are missing](https://github.com/BerryUIKI/AI-Studio/issues/111) |
| F12 | P1 | Reproduced | [#112: Bug: Validate engine installation completion and preserve live install state](https://github.com/BerryUIKI/AI-Studio/issues/112) |
| F13 | P1 | Reproduced | [#113: Bug: Verify model download integrity before promoting an artifact](https://github.com/BerryUIKI/AI-Studio/issues/113) |
| F14 | P1 | Reproduced + Code | [#114: Bug: Protect active creative tasks during engine updates and restore full runtimes](https://github.com/BerryUIKI/AI-Studio/issues/114) |
| F15 | P1 | Code | [#115: Bug: Respect shutdown refusal, process ownership, and Keep Running](https://github.com/BerryUIKI/AI-Studio/issues/115) |
| F16 | P1 | Code | [#116: Bug: Resume workflow subscriptions without resubmitting execution on reconnect](https://github.com/BerryUIKI/AI-Studio/issues/116) |
| F17 | P1 | Reproduced | [#117: Bug: Fail workflows with missing runners and validate execution contracts](https://github.com/BerryUIKI/AI-Studio/issues/117) |
| F18 | P1 | Code + Risk | [#118: Bug: Package a complete portable runtime and verify clean-machine startup](https://github.com/BerryUIKI/AI-Studio/issues/118) |
| F19 | P1 | Code | [#119: Security: Validate uploaded media and isolate active content from the app origin](https://github.com/BerryUIKI/AI-Studio/issues/119) |
| F20 | P2 | Reproduced + Code | [#120: Enhancement: Persist task transitions and generation history across restart](https://github.com/BerryUIKI/AI-Studio/issues/120) |
| F21 | P2 | Code | [#121: Enhancement: Return task IDs at submission and expose accurate cancellation states](https://github.com/BerryUIKI/AI-Studio/issues/121) |
| F22 | P2 | Code | [#122: Refactor: Share a canonical execution and cache-validity contract with planning](https://github.com/BerryUIKI/AI-Studio/issues/122) |
| F23 | P2 | Reproduced + Code | [#123: Bug: Use actual image dimensions and honor the selected upscale factor](https://github.com/BerryUIKI/AI-Studio/issues/123) |
| F24 | P2 | Code | [#124: Bug: Restore complete canvas transactions with undo and redo](https://github.com/BerryUIKI/AI-Studio/issues/124) |
| F25 | P2 | Reproduced + Code | [#125: Bug: Persist engine configuration before showing a successful save](https://github.com/BerryUIKI/AI-Studio/issues/125) |
| F26 | P2 | Code | [#126: Bug: Make Uninstall and Open Folder perform their advertised actions](https://github.com/BerryUIKI/AI-Studio/issues/126) |
| F27 | P2 | Code | [#127: Bug: Resolve lifecycle and execution through the selected engine connection](https://github.com/BerryUIKI/AI-Studio/issues/127) |
| F28 | P2 | Reproduced + Code | [#128: Bug: Persist library and connection settings and apply selected mirrors](https://github.com/BerryUIKI/AI-Studio/issues/128) |
| F29 | P2 | Reproduced | [#129: Bug: Preserve unknown model compatibility and validate readiness dependencies](https://github.com/BerryUIKI/AI-Studio/issues/129) |
| F30 | P2 | Code + Browser | [#130: Enhancement: Connect Model Hub discovery to installation, selection, and truthful estimates](https://github.com/BerryUIKI/AI-Studio/issues/130) |
| F31 | P2 | Browser + Code | [#131: Enhancement: Guide first-time users to a validated first image](https://github.com/BerryUIKI/AI-Studio/issues/131) |
| F32 | P2 | Product assessment | [#132: Enhancement: Prioritize the verified image workflow in first-release navigation](https://github.com/BerryUIKI/AI-Studio/issues/132) |
| F33 | P2 | Code + Browser | [#133: Bug: Report observed progress, real engine logs, and service health](https://github.com/BerryUIKI/AI-Studio/issues/133) |
| F34 | P2 | Code | [#134: Bug: Preserve Agent conversation identity and place outputs in project context](https://github.com/BerryUIKI/AI-Studio/issues/134) |
| F35 | P2 | Reproduced + Code | [#135: Bug: Complete embedded LLM lifecycle results and readiness checks](https://github.com/BerryUIKI/AI-Studio/issues/135) |
| F36 | P2 | Code | [#136: Bug: Render and export managed media using verified MIME and format metadata](https://github.com/BerryUIKI/AI-Studio/issues/136) |
| F37 | P2 | Browser; qualitative assessment | [#137: Enhancement: Improve canvas information hierarchy and resilient visual feedback](https://github.com/BerryUIKI/AI-Studio/issues/137) |
| F38 | P2 | Browser + Code | [#138: Enhancement: Standardize accessible dialogs and scope canvas keyboard shortcuts](https://github.com/BerryUIKI/AI-Studio/issues/138) |
| F39 | P2 | Browser + Code | [#139: Enhancement: Align advertised language support with complete workflow translations](https://github.com/BerryUIKI/AI-Studio/issues/139) |
| F40 | P2 | Code | [#140: Performance: Move blocking inventory and hardware work off async request paths](https://github.com/BerryUIKI/AI-Studio/issues/140) |
| F41 | P2 | Code + Build | [#141: Performance: Limit store subscriptions, polling, and inactive-view effects](https://github.com/BerryUIKI/AI-Studio/issues/141) |
| F42 | P2 | Code | [#142: Refactor: Consolidate typed execution, lifecycle, and API contracts](https://github.com/BerryUIKI/AI-Studio/issues/142) |
| F43 | P2 | Code + Validation | [#143: Test: Gate release verification on current-head end-to-end acceptance](https://github.com/BerryUIKI/AI-Studio/issues/143) |
| F44 | P2 | Risk | [#144: Validation: Verify native capabilities and CSP on the production backend origin](https://github.com/BerryUIKI/AI-Studio/issues/144) |

The screenshot and original 640 x 360 fixture are attached to F23. All source references are pinned to commit c1c5dbeaace01fc5e3fa68d8e3ebf410583b775b.
