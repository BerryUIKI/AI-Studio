"""Prepare English GitHub issue drafts from the 2026-10-05 review."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SHA = "c1c5dbeaace01fc5e3fa68d8e3ebf410583b775b"
REPO = "BerryUIKI/AI-Studio"
BASE = f"https://github.com/{REPO}"

# ID: title, labels, reproduction/validation, acceptance criteria.
DETAILS: dict[int, tuple[str, list[str], str, list[str]]] = {
    1: (
        "Security: Protect stored credentials and make API secret fields write-only",
        ["security", "bug", "backend", "critical"],
        "An isolated CredentialManager saved a dummy value to its JSON file without encryption. A FastAPI TestClient request to the LLM configuration read API returned that same dummy value. No real credential was accessed. Public evidence is limited to this remediation summary; no credential or exploit payload is included.",
        ["Persist secrets using an appropriate OS-backed facility and document platform behavior.", "GET and save responses return only redacted/configured state, never a complete secret.", "Failed persistence produces an actionable error rather than reporting a durable save.", "Regression tests cover response, log, project, and export redaction."]),
    2: (
        "Security: Enforce a session boundary for local control APIs and WebSockets",
        ["security", "bug", "backend", "critical"],
        "Isolated handler tests accepted an unrelated Origin on a control POST and on an execution WebSocket. The fixture had no installed engine, so no engine was started. This demonstrates missing application-side checks, not a complete browser exploit; private-network restrictions can affect browser reachability.",
        ["Require a per-launch session credential for sensitive reads and mutations.", "Validate browser origins for mutations and WebSocket handshakes.", "Unauthorized execution, install, stop, shutdown, and secret reads are rejected.", "Supported desktop/browser origins continue to work without widening access."]),
    3: (
        "Bug: Verify engine process ownership before terminating a stored PID",
        ["bug", "security", "backend", "critical"],
        "On Windows, run an isolated Python process and pass os.getpid() to ComfySupervisor._verify_process_identity and WebUISupervisor._verify_process_identity. Both returned True for the unrelated probe process. Do not call stop or taskkill during this validation; no real process was terminated by the probe.",
        ["Verify executable/runtime path, process creation time, command line, and ownership before termination.", "A recycled or ambiguous PID is treated as unowned.", "Stopping an owned engine does not affect external engines or unrelated Python processes.", "Tests simulate stale PID files without terminating real processes."]),
    4: (
        "Bug: Save and reopen the complete canvas as a durable project",
        ["bug", "frontend", "backend", "critical"],
        "1. Open Berry with a disposable data directory.\n2. Add a Text Input canvas item and change its position/content.\n3. Reload the browser and return to the canvas.\n4. Observe that the item and layout are gone.\nThe frontend canvas store initializes in memory and does not call the backend project CRUD routes.",
        ["Users can create, save, open, and autosave a versioned project.", "Restart restores layout, asset references, lineage, and generation history.", "Missing imported files produce an actionable recovery state.", "An end-to-end restart test exercises the actual frontend project flow."]),
    5: (
        "Bug: Transfer source images and masks into ComfyUI before execution",
        ["bug", "backend", "critical"],
        "Trace an imported managed asset through CreativeRunner._run_comfy into the compiled LoadImage nodes. The graph uses the asset basename, but ComfyUI is launched with a separate engine/input directory. There is no upload/copy bridge in the reviewed path. Live GPU inference was not run; validate using a managed engine and a separately owned external engine.",
        ["Upload/adopt each source and mask through the selected engine's input contract.", "Use the filename returned by the engine rather than a Berry storage basename.", "Imported img2img, inpaint, and upscale complete on managed and external ComfyUI.", "Transfer errors preserve the source and report an actionable failure."]),
    6: (
        "Bug: Normalize painted inpainting masks for each provider",
        ["bug", "backend", "frontend", "critical"],
        "1. Start with the transparent InpaintModal mask canvas.\n2. Paint a small opaque white region.\n3. Trace the saved mask into the compiled LoadImage MASK output.\n4. Upstream ComfyUI computes MASK as 1-alpha: the painted region becomes 0 and the unpainted region becomes 1.\nThis is a source/contract check; a real engine output has not yet been validated.",
        ["Document a canonical edit/protect meaning for Berry masks.", "Convert explicitly for ComfyUI, WebUI, and supported cloud-provider conventions.", "A known-region integration test edits the painted area and preserves the intended surrounding area.", "Source/mask dimensions and coordinates remain aligned through resizing."]),
    7: (
        "Bug: Connect downloaded and shared model directories to engine search paths",
        ["bug", "backend", "critical"],
        "Compare ModelDownloader target paths with the managed supervisors' launch arguments. ComfyUI downloads use engine/models without corresponding extra-model-path configuration. WebUI download paths are rooted under the home-directory engine tree while its supervisor uses the configured engine root. Adding a scan root only indexes files. Real model loading remains an integration test to perform.",
        ["Resolve download, scan, and execution paths through one engine/path registry.", "Configure shared ComfyUI paths and WebUI model directories consistently.", "A newly downloaded compatible model appears in engine discovery and runs without manual relocation.", "Custom roots work by reference where supported and never imply compatibility from location alone."]),
    8: (
        "Bug: Correct managed WebUI launch flags and isolated Python compatibility",
        ["bug", "backend", "critical"],
        "Inspect WebUISupervisor.start: it passes --listen followed by 127.0.0.1 and --nowebui. Upstream defines --listen as a boolean and provides a separate server-name option; --nowebui disables the promised native UI. The installer creates the engine venv from Berry's interpreter, which was Python 3.14.5 during review, while upstream Windows launch checks target Python 3.10. No GPU installation was attempted.",
        ["Pin a supported engine revision and provision its supported interpreter in the isolated runtime.", "Use the correct loopback binding flags.", "Both API health and the advertised native WebUI are verified after deployment.", "Unsupported prerequisites fail preflight with actionable guidance."]),
    9: (
        "Bug: Apply the selected WebUI checkpoint and record the effective model",
        ["bug", "backend", "critical"],
        "Use httpx.MockTransport to capture WebUIRunner._run_txt2img for model=chosen-checkpoint.safetensors and seed=42. Return a dummy base64 image. The captured request has neither override_settings nor sd_model_checkpoint. The fixture did not contact WebUI. Inspect img2img/inpaint for the same selected-model contract.",
        ["Validate and apply the selected checkpoint using WebUI's supported API.", "Record/cache the effective model used, including an appropriate revision identity.", "Requests for two distinct checkpoints produce the corresponding selection contract.", "Unavailable models fail before generation rather than silently using a previously loaded checkpoint."]),
    10: (
        "Bug: Use one provider resolution plan for dispatch, hashing, and provenance",
        ["bug", "backend", "architecture", "critical"],
        "1. Construct a txt2img request with engine_id=fal_ai, model=sdxl-turbo, and seed=42.\n2. Mock both credential lookups with dummy values and mock Fal/SiliconFlow calls.\n3. Compare resolve_effective_provider(request) with CreativeRunner._run_cloud dispatch.\nObserved: resolver=Fal; executed mock=SiliconFlow. No paid API call was made.",
        ["Resolve one capability-checked execution plan before submission.", "Dispatch, cache keys, provenance, and UI disclosure use that same plan.", "Explicit provider selection cannot silently switch to another service.", "Tests cover multiple configured providers and unsupported model/action combinations."]),
    11: (
        "Bug: Invalidate cached results whose output assets are missing",
        ["bug", "backend", "critical"],
        "1. In a disposable asset/cache database, execute a seed=42 request with the engine mocked to return a managed fixture asset.\n2. Delete only that fixture's output file.\n3. Submit the identical request.\nObserved: success=True, is_cached=True, old asset URL, and only one engine call although the file is absent.",
        ["A cache hit requires all referenced outputs to remain available and valid.", "Broken entries are invalidated and recomputed or returned as an actionable missing-output state.", "Startup reconciliation detects orphaned references.", "Tests cover deleted/corrupt outputs and valid reuse across restarts."]),
    12: (
        "Bug: Validate engine installation completion and preserve live install state",
        ["bug", "backend", "critical"],
        "Two isolated probes expose the installation-state contract. (1) Create an empty ComfyUI destination and mock venv creation as successful; install_engine reports completed with no main.py. (2) Write a DOWNLOADING manifest and read it through read_manifest; it becomes INTERRUPTED even though a live status read should not invalidate an active worker. No repository clone or package installation was performed.",
        ["Distinguish active installation workers from interrupted previous runs.", "Status reads are side-effect-free for active installations.", "Missing entrypoint, dependency setup, or validation prevents completed state.", "Per-engine locking and staged promotion preserve existing working installations.", "Interrupted and empty-directory retries recover without false success."]),
    13: (
        "Bug: Verify model download integrity before promoting an artifact",
        ["bug", "backend", "critical"],
        "Construct a HubModelRecord declaring size_bytes=100 and an explicit SHA-256. Feed DownloadWorker a mocked 13-byte corrupt HTTP response. Observed: status=completed and a promoted 13-byte destination. No model was downloaded from the network. Also inspect partial-file resume/source switching and replacement of an existing destination.",
        ["Validate expected length and checksum where supplied before promotion.", "Reject incompatible Content-Range, ETag/source identity, or resume responses.", "Promotion is atomic and preserves a previous valid model on failure.", "Invalid downloads remain failed/incomplete with actionable diagnostics."]),
    14: (
        "Bug: Protect active creative tasks during engine updates and restore full runtimes",
        ["bug", "backend", "critical"],
        "Insert a disposable creative task into creative_runner.active_tasks while leaving workflow cancellations empty. Mock installer.update_engine and capture has_active_tasks_fn(). It returns False. No real update was run. Source review also shows dependency mutation followed by source-only git checkout on rollback, leaving the environment unrecovered.",
        ["Workflow and creative tasks share one authoritative lifecycle registry.", "An exclusive update lease rejects work/update races and rechecks live state.", "Update stages a complete compatible runtime before switching.", "Rollback restores code and dependencies and leaves the engine in a recoverable state."]),
    15: (
        "Bug: Respect shutdown refusal, process ownership, and Keep Running",
        ["bug", "backend", "frontend", "critical"],
        "Trace the desktop close command into shutdown_backend. It posts force=false, discards the response, waits 500 ms, and kills its owned child. Keep Running uses the same close path. The helper sends a shutdown request even when no child is owned. This was code-reviewed; a native application was not closed against a real task. Validate with mocked HTTP 409 and child-process handles first.",
        ["Keep Running preserves the intended backend/engine processes.", "A graceful shutdown refusal cannot lead to an implicit forced kill.", "An unowned/pre-existing backend is never shut down by window cleanup.", "Titlebar close, Alt+F4, window destruction, and active tasks obey the same explicit policy."]),
    16: (
        "Bug: Resume workflow subscriptions without resubmitting execution on reconnect",
        ["bug", "frontend", "backend", "critical"],
        "Inspect useCanvasStore.runWorkflow: every WebSocket onopen sends the full run payload. The server accepts a submission again rather than resuming a durable run, and UI events are not isolated by run ID. Client PINGs are also sent after the server stops receiving messages. Duplicate paid execution was not attempted; validate with a controllable connection and a counted fake runner.",
        ["Separate idempotent submission from subscription/resume.", "Reconnect to an existing durable run without a second inference call.", "Ignore stale events from previous runs.", "Implement a matched heartbeat protocol or remove the unsupported heartbeat.", "Disconnect/reconnect tests assert execution count and final state."]),
    17: (
        "Bug: Fail workflows with missing runners and validate execution contracts",
        ["bug", "backend", "critical"],
        "Submit an isolated WebSocket graph with one node of unknown type review.unknown and no edges. Read events through GRAPH_FINISHED. Observed: a no-runner node error followed by final status=completed. The probe submitted no engine work. Extend preflight coverage to required ports, types, duplicate/dangling references, and unavailable runners.",
        ["Reject unsupported node/runner contracts before inference.", "Final graph status reflects all node failures and cancellation outcomes.", "Dependents of failed nodes are consistently blocked.", "Tests assert node and graph outcomes for missing runners and invalid ports/references."]),
    18: (
        "Bug: Package a complete portable runtime and verify clean-machine startup",
        ["bug", "backend", "architecture", "critical"],
        "Review package-windows-release.ps1: it stages a development venv/config, allows missing Python staging with a warning, and builds the native binary before frontend assets. An isolated copy of the venv executable/config executed successfully only with sys.base_prefix outside that copy, confirming base-runtime dependence. This is not a clean-VM launch failure; a clean Windows VM still needs testing. Git provisioning for engine setup must also be established.",
        ["Package a pinned complete redistributable Python runtime and all prerequisites.", "Build frontend assets before native embedding and fail incomplete staging.", "Remove dependency on developer-machine interpreter paths.", "Run startup, cloud onboarding, installation prerequisites, and safe exit on a Windows VM without Python/Git/Node development tools.", "Smoke-test reporting distinguishes host-machine checks from clean-machine acceptance."]),
    19: (
        "Security: Validate uploaded media and isolate active content from the app origin",
        ["security", "bug", "backend", "critical"],
        "Code inspection found whole-payload reads without byte/pixel limits, no image-decoder validation, user-provided media types, and inline responses based on filename MIME inference. Base64 upload has similar gaps. No malicious content was executed; this public report does not include an exploit payload.",
        ["Enforce bounded upload/base64 byte and decoded-pixel limits.", "Validate/normalize supported image/video formats before adoption.", "Do not serve executable uploaded content with application-origin privileges.", "Set explicit MIME, content-disposition, and security headers.", "Tests cover malformed, oversized, and unsupported media without executing active content."]),
    20: (
        "Enhancement: Persist task transitions and generation history across restart",
        ["enhancement", "backend", "architecture"],
        "Execute a creative fixture through a mocked runner using an isolated database, then query SELECT COUNT(*) FROM runs and tasks. Both remained zero. Active task/download-worker state is stored in memory. No real provider job was submitted.",
        ["Persist effective inputs, task transitions, provider job IDs, errors, and output references.", "Restart reconciles interrupted local/remote work.", "Retry and cancellation retain an identifiable durable task.", "Expose project-linked generation/task history and test restart recovery."]),
    21: (
        "Enhancement: Return task IDs at submission and expose accurate cancellation states",
        ["enhancement", "backend", "frontend"],
        "Trace creative submission and cancel_task. The POST returns its task ID after execution finishes, while cancellation is checked after awaited execution. Cloud work can continue after a local cancelled response; Comfy interrupt is not scoped to a queued task. Validate with a blocking fake runner and a provider that does not support remote cancellation.",
        ["Return an identifiable task immediately and stream status independently.", "The UI can request cancellation while creation is running.", "Distinguish cancel-requested from confirmed cancellation and disclose remote limitations.", "Use bounded queue/concurrency and task-specific ownership where engine APIs allow it."]),
    22: (
        "Refactor: Share a canonical execution and cache-validity contract with planning",
        ["architecture", "backend", "enhancement"],
        "Compare generate_plan with workflow/creative execution: planning uses upstream computation state and memory lookup; execution uses output-derived state and persistent lookup. String asset URLs are hashed as strings, model identities are names, and runner versions default to a constant. This is a contract review, not a measured live cache-collision incident.",
        ["Plan and execute from the same canonical resolved specification.", "Use verified port-aware content identities and effective model/runtime revisions.", "Planning reports only valid persistent cache hits.", "Stable URLs with changed content and replaced same-name models invalidate reuse.", "Expose explicit Reuse/New Variation semantics without layout-triggered inference."]),
    23: (
        "Bug: Use actual image dimensions and honor the selected upscale factor",
        ["bug", "frontend", "backend", "ui/ux"],
        "1. Open Berry with an empty disposable library.\n2. Import the attached 640 x 360 PNG.\n3. Select the image and open Upscale.\n4. Choose 2x.\nObserved: Current=512 x 512 and Target=1024 x 1024.\nSeparately, aspect-ratio normalization overwrites action dimensions and the Comfy upscale graph uses the upscaler's native factor without applying the requested scale. No real upscale inference was run.",
        ["Decode and store actual adopted-image dimensions.", "The upscale preview preserves source ratio and reflects the requested factor.", "Apply the requested factor explicitly when an upscaler has a different native scale.", "Derive result metadata from decoded output rather than requested dimensions.", "Test non-square imports and both supported upscale factors end to end."]),
    24: (
        "Bug: Restore complete canvas transactions with undo and redo",
        ["bug", "frontend", "ui/ux"],
        "Inspect history snapshots: they contain nodes only. A node deletion also removes its edges, but undo restores nodes without those edges. Movement and some imported/generated insertions use different mutation paths. Validate by creating connected items, deleting one, undoing, and comparing the complete canvas state.",
        ["Define transactions for movement, connections, grouping, imports, generation insertion, and deletion.", "Undo/redo restores affected nodes, edges, relationships, and selection together.", "A single user action produces a predictable history entry.", "Rendered workflow tests cover deletion/restore and generated/imported additions."]),
    25: (
        "Bug: Persist engine configuration before showing a successful save",
        ["bug", "frontend", "backend", "ui/ux"],
        "1. Open the managed WebUI configuration dialog.\n2. Observe the initial port (8188 in the reviewed UI).\n3. Change a setting and click Save Configuration.\n4. Observe the success message even though App supplies no onSave handler.\nThe modal's useState also does not synchronize with the selected instance.",
        ["Load the chosen instance's current port and arguments.", "Save through a real backend persistence operation.", "Show pending/error/success from the actual result.", "Reopening/restarting retains the saved configuration and execution uses it."]),
    26: (
        "Bug: Make Uninstall and Open Folder perform their advertised actions",
        ["bug", "frontend", "ui/ux"],
        "Inspect App.handleUninstallEngine: external entries are unbound, but managed entries call stop rather than uninstall. The embedded Open install folder action routes to management instead of opening that directory. This was source-reviewed; no user's installation was removed.",
        ["Separate Stop, Remove Connection, Open Folder, and Uninstall contracts.", "Managed uninstall removes only the intended managed runtime with explicit retained-data behavior.", "External removal remains non-destructive.", "Open Folder opens the actual configured directory or explains its absence."]),
    27: (
        "Bug: Resolve lifecycle and execution through the selected engine connection",
        ["bug", "backend", "frontend", "architecture"],
        "Trace an external engine ID through frontend start/stop, creative execution, and EmbeddedEngineView. Frontend lifecycle selects managed routes by type, runners use default clients, the embedded URL is reconstructed from localhost/port, and WebUI start callbacks in App use the Comfy toggle. Validate with two mocked endpoints and assert the chosen connection receives the request.",
        ["Carry one stable connection ID through all execution/lifecycle calls.", "Use its endpoint, native URL, capabilities, ownership, and configuration.", "Do not start/stop managed engines when an external connection is selected.", "WebUI buttons dispatch WebUI operations.", "Tests cover non-default hosts/ports and both managed/external connections."]),
    28: (
        "Bug: Persist library and connection settings and apply selected mirrors",
        ["bug", "backend", "frontend"],
        "Add a custom root to ModelStore, reconstruct ModelStore using the same engine directory, and inspect roots: the custom root is missing. Connections/mirror settings are also memory-only. Source review found install/deploy paths that do not consume selected Git/PyPI mirror settings. Only disposable model-root reconstruction was executed.",
        ["Persist roots, connections, and mirror preferences with stable identities.", "Restart restores configuration without mutating user-owned installations.", "Advertised mirror selections control the corresponding download/install requests.", "Tests capture Git, Python-package, and model source selection without real installations."]),
    29: (
        "Bug: Preserve unknown model compatibility and validate readiness dependencies",
        ["bug", "backend", "ui/ux"],
        "1. Write the bytes not-a-real-model to a disposable unknown.gguf file.\n2. Add its directory as a ModelStore root and scan.\n3. Inspect the record.\nObserved: is_ready=True, architecture=unknown, engine_compatibility=[comfyui].\nFLUX dependencies are separately listed as missing without resolving actual inventory or bundled components.",
        ["Distinguish integrity, recognized format, architecture, dependencies, and tested compatibility.", "Invalid or unknown files cannot be shown as ready by default.", "Resolve required dependencies against available/bundled components.", "Use content/revision identity for models rather than path plus size alone."]),
    30: (
        "Enhancement: Connect Model Hub discovery to installation, selection, and truthful estimates",
        ["enhancement", "frontend", "backend", "ui/ux"],
        "Inspect ModelHubView and catalog/inventory integration: default Use Cloud only logs, install state is not reconciled into catalog state, and downloads do not establish a selected canvas model. LLM entries have no category tab. Hardware evaluation uses total VRAM and fixed speed bands despite receiving free VRAM. No latency benchmark was performed.",
        ["Refresh real installed/readiness state after download.", "Use Model/Use Provider validates capabilities and configures the canvas.", "Support the intended target engine and model categories.", "Performance estimates use documented workload/device assumptions and available resources.", "Unmeasured estimates are labeled as estimates rather than guaranteed latency."]),
    31: (
        "Enhancement: Guide first-time users to a validated first image",
        ["enhancement", "frontend", "ui/ux"],
        "Open Berry with no engines/models/keys configured. The empty canvas has no clear first task, Generate can target an uninstalled default engine, model entry exposes a filename, and Cloud is generic despite differing provider capabilities. Browser observation and code review were used; no paid generation was submitted.",
        ["Provide clear cloud/local setup and a first-image action.", "Select only ready compatible providers/models or offer a direct repair path.", "Basic controls match the chosen action/provider capabilities.", "A clean user reaches a first cloud image without local GPU dependencies or node wiring."]),
    32: (
        "Enhancement: Prioritize the verified image workflow in first-release navigation",
        ["enhancement", "frontend", "ui/ux", "architecture"],
        "Product assessment against PRODUCT_VISION/PRD/ROADMAP: Video, Agent, engine internals, model setup, and node-oriented views compete in primary navigation while the approved image/project journey remains incomplete. This is a scope/UX proposal, not a runtime crash claim.",
        ["Define the primary project -> create/import -> select/edit -> export journey.", "Place engine internals in secondary navigation with clear readiness states.", "Identify experimental/unverified feature combinations and their availability.", "Validate the navigation with first-use tasks and the first-release PRD."]),
    33: (
        "Bug: Report observed progress, real engine logs, and service health",
        ["bug", "frontend", "backend", "ui/ux"],
        "Inspect the creative progress timer: it invents checkpoint/latent/VAE stages regardless of engine events, including cloud runs. EngineManager.get_logs returns placeholder ready/verified messages when supervisors have no log method, while stdout/stderr is discarded. These code paths were reviewed; fake-ready output is not evidence that any engine was actually healthy.",
        ["Display observed phases or an honest indeterminate waiting state.", "Do not expose low-level latent/VAE stages on the primary creative canvas.", "Retain bounded redacted real logs and never replace missing diagnostics with verification claims.", "Distinguish installed, starting, process-running, and service-healthy states.", "A failed/hung engine provides actionable diagnostics."]),
    34: (
        "Bug: Preserve Agent conversation identity and place outputs in project context",
        ["bug", "frontend", "backend", "ui/ux"],
        "Inspect AgentPanel chat POST bodies: they contain message and selected_asset_id but omit conversation_id. AgentService creates a new UUID when it is absent, so a second UI message starts a fresh backend conversation despite visible history. Panel state is transient, server retention is unbounded, and proposal insertion uses fixed coordinates.",
        ["Retain and resend conversation_id for subsequent messages.", "Define project-linked persistence and bounded conversation retention.", "Accepted proposals use the shared task lifecycle.", "Place outputs near the relevant selection without repeated overlap.", "A follow-up message demonstrably retains prior context."]),
    35: (
        "Bug: Complete embedded LLM lifecycle results and readiness checks",
        ["bug", "backend", "frontend"],
        "Mock LlamaServerSupervisor.get_pid, subprocess.run, and PID cleanup, then call stop: successful termination returns None despite its dictionary annotation. No real process was terminated. Source review also found automatic startup of the first local model, fixed-port use, and no awaited readiness before reporting start success.",
        ["All start/stop paths return explicit structured results.", "Local startup follows a saved opt-in preference and selected model.", "Check port ownership and service readiness independently of PID existence.", "Provider configuration is not presented as readiness when runtime/model is missing.", "Tests cover absent/starting/healthy/failed services and successful stop."]),
    36: (
        "Bug: Render and export managed media using verified MIME and format metadata",
        ["bug", "frontend", "backend", "ui/ux"],
        "Inspect ImageCardNode with mediaType=video and a managed URL such as /api/v1/assets/<id>/content. Its extension test cannot identify animated WebP at that URL and selects the video element. Explicit .webp/.gif URLs are already handled separately. FloatingCardToolbar forces png/mp4 names, and image-card export often guesses from an extensionless URL. This is code evidence, not a live generated-video reproduction.",
        ["Track verified MIME, codec, and extension in the asset/card contract.", "Render animated images and playable video using media metadata, including extensionless URLs.", "Export original content with a correct extension or perform an explicit conversion.", "Provider upload MIME matches decoded source content.", "Tests cover JPEG, animated WebP, GIF, and MP4 managed assets."]),
    37: (
        "Enhancement: Improve canvas information hierarchy and resilient visual feedback",
        ["enhancement", "frontend", "ui/ux"],
        "Browser review at approximately 1060 x 612 found small toolbar/action text, advanced controls competing with the canvas, dock/minimap competition, and large blank model previews after thumbnail errors. These are qualitative observations; the native minimum 1024 x 700 layout was not exercised and no failure at that minimum is claimed.",
        ["Establish a clear primary action and progressive disclosure for advanced controls.", "Provide meaningful local thumbnail fallbacks.", "Consolidate task/readiness feedback in a discoverable area.", "Validate native minimum size, common laptop sizes, and 125%/150% display scaling.", "Record task-based usability evidence before declaring layout acceptance."]),
    38: (
        "Enhancement: Standardize accessible dialogs and scope canvas keyboard shortcuts",
        ["accessibility", "enhancement", "frontend", "ui/ux"],
        "Review dialog roles, focus behavior, input labeling, icon-control names, and keyboard activation of clickable cards. Several implementations lack a common accessible contract. ViewContainer keeps hidden canvas views mounted, so global shortcut handlers remain active and do not cover all editable/focusable contexts. Validate through keyboard-only workflows and the accessibility tree.",
        ["Dialogs expose appropriate semantics, focus trapping/restoration, and Escape handling.", "Inputs and icon-only controls have meaningful accessible names.", "Cards/actions are keyboard-operable.", "Canvas shortcuts only act in the active canvas and respect editable focus.", "Keyboard-only create/edit/cancel/export/navigation passes."]),
    39: (
        "Enhancement: Align advertised language support with complete workflow translations",
        ["enhancement", "frontend", "ui/ux"],
        "Switch among the advertised locales and inspect the creation/configuration/model workflows. Settings offers multiple languages while significant canvas/error/dialog text remains hardcoded in English and some launcher/model labels remain Chinese. This was browser/source reviewed rather than a full translation-quality audit.",
        ["Advertise only languages with defined coverage.", "Route product-facing strings through one locale system with documented fallbacks.", "Format dates/numbers/errors consistently.", "Validate every primary workflow in each supported locale."]),
    40: (
        "Performance: Move blocking inventory and hardware work off async request paths",
        ["performance", "backend"],
        "Trace manager/model routes into synchronous scans and hardware subprocess calls; async asset methods also perform synchronous file writes/hashing. Status requests rescan inventory. No load/latency benchmark was run, so this issue identifies an event-loop blocking risk rather than claiming a measured latency number.",
        ["Run blocking operations in bounded workers.", "Maintain an incremental model index and cached status/hardware snapshots.", "Avoid full inventory scans on routine status polling.", "Measure health/task latency during representative large scans and imports."]),
    41: (
        "Performance: Limit store subscriptions, polling, and inactive-view effects",
        ["performance", "frontend"],
        "App and canvas components subscribe to whole stores; progress changes can notify unrelated views. ViewContainer mounts all views and hides inactive ones while effects/listeners continue. Independent polling and full node history snapshots add work. The reviewed production build's JS chunk was 645.91 kB (184.78 kB gzip); no startup/frame-time benchmark was run.",
        ["Use focused Zustand selectors and shared polling.", "Suspend inactive-view effects/listeners and lazy-load secondary views where appropriate.", "Profile a representative large canvas and idle/active-view behavior.", "Document measured improvements without treating bundle size alone as a startup failure."]),
    42: (
        "Refactor: Consolidate typed execution, lifecycle, and API contracts",
        ["architecture", "enhancement", "backend", "frontend"],
        "main.py combines routing and orchestration with globally owned services; provider/cancellation/lifecycle rules are repeated across entry points, and two Rust implementations manage backends. Engine identifier/response contracts vary. Remaining unrestricted any uses and style/type-rule gaps are also not consistently enforced. This is a maintainability assessment with concrete duplicated contracts, not a request for a broad formatting rewrite.",
        ["Define typed services for execution plans, durable tasks, engine lifecycle/connections, and assets.", "Keep routes thin and remove duplicate decision trees.", "Align frontend/backend engine identities and response contracts.", "Enforce targeted typing/style rules with documented exceptions.", "Keep refactoring commits separate from behavioral fixes and preserve public behavior with meaningful contract tests."]),
    43: (
        "Test: Gate release verification on current-head end-to-end acceptance",
        ["enhancement", "documentation", "backend", "frontend"],
        "The review baseline passed 157 backend tests, 41 frontend tests, 3 launcher tests, frontend build/lint, and Tauri cargo check. Nevertheless the current probes reproduce missing project durability, invalid cache reuse, false install completion, and model/provider mismatches. RELEASE_VERIFICATION_REPORT marks R01-R18 verified using mixed mocks, primitive tests, source inspection, and builds; that is not full user acceptance.",
        ["Map each PRD requirement to a specific acceptance test and evidence level.", "Record tested commit, environment, provider/engine versions, and output artifacts.", "Gate release on first image, reopen, masked edit, upscale/export, ownership, recovery, and safe exit.", "Run a packaged clean-machine desktop journey.", "Historical/mocked verification is clearly distinguished from current live integration evidence."]),
    44: (
        "Validation: Verify native capabilities and CSP on the production backend origin",
        ["question", "security", "frontend", "architecture"],
        "The native window navigates to an HTTP backend origin, while default capabilities declare window permissions without a remote URL scope and CSP is disabled. Tauri documents explicit capability configuration for remote sources. Native production commands were not executed, so this is an integration-validation task rather than an observed broken window-control report.",
        ["Exercise the packaged production origin and intended native commands.", "Grant only the required narrowly scoped capabilities to the supported local origin.", "Configure an appropriate CSP and isolate untrusted media/content.", "Verify minimize/maximize/drag/close plus failure paths in the packaged application."]),
}

RELATED: dict[int, tuple[int, str]] = {
    2: (58, "The earlier wildcard-CORS issue is closed. This report concerns application session/origin authorization remaining after that configuration change."),
    10: (59, "The earlier missing-provider-hash issue is closed. This report concerns disagreement between the resolver now used for hashing and the actual dispatch tree."),
    16: (67, "Reconnect/heartbeat support was previously requested and the issue is closed. This report concerns resubmission and an unmatched heartbeat contract in the resulting implementation."),
    24: (36, "Shortcut/history support was previously requested. This report concerns incomplete restoration of the complete canvas state."),
    25: (72, "The earlier hardcoded-port issue is closed. This report concerns unsynchronized modal state and a save operation with no persistence handler."),
    27: (72, "This follows up connection identity/endpoint propagation beyond the earlier fixed port literals."),
    33: (37, "Real execution stages were previously requested. This report concerns simulated stages and placeholder diagnostics rather than observed progress."),
    34: (38, "This follows up actual conversation continuity and project-context output placement rather than introducing another spatial-agent feature request."),
    35: (96, "Embedded llama-server was implemented. This report concerns remaining lifecycle result and readiness contracts."),
    41: (66, "The earlier JSON-cloning issue is closed and structuredClone is now used. This report concerns whole-store updates, inactive views, polling, and snapshot volume rather than that already-fixed cloning method."),
    42: (63, "The earlier typing issue is closed. Remaining any uses and duplicated service contracts are current-head follow-up work, not a claim that none of the prior typing work occurred."),
}

EXTRA_SOURCES: dict[int, list[tuple[str, int | None]]] = {
    6: [("frontend/src/components/canvas/InpaintModal.tsx", 77)],
    18: [("scripts/smoke-test-package.ps1", 83)],
    21: [("frontend/src/stores/useCreativeStore.ts", 173), ("backend/app/main.py", 759)],
    27: [("frontend/src/stores/useEngineStore.ts", 120), ("backend/app/runners/creative_runner.py", 345)],
    28: [("backend/app/runtime/engine_manager.py", 30), ("backend/app/runtime/installer.py", 358)],
    30: [("frontend/src/components/hub/ModelHubView.tsx", 82), ("backend/app/storage/hub_catalog.py", 7)],
    31: [("frontend/src/components/canvas/CreationDock.tsx", None), ("frontend/src/stores/useCreativeStore.ts", 129)],
    32: [("docs/PRD.md", 7), ("frontend/src/App.tsx", 289), ("docs/ROADMAP.md", None)],
    34: [("backend/app/core/agent_service.py", 188)],
    35: [("backend/app/runtime/llama_server/llama_supervisor.py", 263)],
    36: [("frontend/src/components/canvas/ImageCardNode.tsx", 183), ("frontend/src/components/canvas/FloatingCardToolbar.tsx", 32), ("backend/app/runners/creative_runner.py", 443)],
    37: [("frontend/src/components/canvas/CreationDock.tsx", None), ("frontend/src/components/hub/HubModelCard.tsx", None)],
    38: [("frontend/src/components/canvas/FlowCanvas.tsx", None), ("frontend/src/components/launcher/EngineConfigModal.tsx", None), ("frontend/src/components/navigation/ViewContainer.tsx", 19)],
    39: [("frontend/src/i18n/translations.ts", None), ("frontend/src/components/settings/SettingsView.tsx", None)],
    40: [("backend/app/runtime/hardware.py", 39)],
    42: [("backend/app/main.py", None), ("launcher/src/backend.rs", None), ("frontend/src-tauri/src/backend.rs", None), ("frontend/src/components/agent/AgentPanel.tsx", 99)],
    43: [("docs/RELEASE_VERIFICATION_REPORT.md", 39), (".github/workflows/ci.yml", None)],
    44: [("frontend/src-tauri/src/lib.rs", 71)],
}


def source_url(path: str, line: int | None = None) -> str:
    """Return an immutable source permalink after checking the local reference."""
    local = ROOT / path
    if not local.is_file():
        raise ValueError(f"Missing source: {path}")
    if line and line > len(local.read_text(encoding="utf-8-sig").splitlines()):
        raise ValueError(f"Invalid source line: {path}:{line}")
    return f"{BASE}/blob/{SHA}/{path}" + (f"#L{line}" if line else "")


def remote_link(match: re.Match[str]) -> str:
    """Replace private workspace links with commit-pinned source links."""
    label, path_ref = match.groups()
    if path_ref.startswith("docs/reviews/"):
        return label
    path, _, line = path_ref.partition(":")
    return f"[{label}]({source_url(path, int(line) if line else None)})"


def prepare() -> None:
    report = (ROOT / "docs/reviews/2026-10-05-product-technical-review.md").read_text(encoding="utf-8-sig")
    sections = re.findall(r"^### F(\d+)\. ([^\n]+)\n\n(.*?)(?=^### F\d+\.|^## First-release|\Z)", report, re.M | re.S)
    assert len(sections) == len(DETAILS) == 44
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    for number, original_title, text in sections:
        finding = int(number)
        title, labels, validation, criteria = DETAILS[finding]
        evidence = re.search(r"\*\*Evidence: ([^*]+)\*\*", text)
        assert evidence
        evidence_label = evidence.group(1).strip().rstrip(".")
        text = re.sub(r"^!\[[^\n]*\n?", "", text, flags=re.M)
        text = re.sub(r"\[([^\]]+)\]\(D:/dev/AI-Studio/([^\)]+)\)", remote_link, text)
        text = text.replace("invented ready/verified", "placeholder ready/verified")
        text = text.replace("advances a timer and displays", "advances a timer and displays")
        priority = "P1 - proposed first-release blocker" if finding <= 19 else "P2 - material improvement or integration validation"
        summary = re.sub(r"^\*\*Evidence: [^*]+\*\*\s*", "", text).split("**Impact:**")[0].strip()
        impact_part = text.split("**Impact:**", 1)[1]
        impact, proposed = impact_part.split("**Acceptance:**", 1)
        impact = impact.strip()
        proposed = proposed.strip()
        impact = impact[:1].upper() + impact[1:]
        proposed = proposed[:1].upper() + proposed[1:]
        body = f"""<!-- berry-review:2026-10-05:F{finding:02} -->
## Summary

{summary}

## Environment and evidence

- Review finding: **F{finding:02}** (2026-10-05 product/technical review).
- Baseline: Windows, `dev` at [{SHA[:7]}]({BASE}/commit/{SHA}). The remote `dev` matched this commit when filing.
- Evidence: **{evidence_label}**.
- Priority recommendation: **{priority}**. This is review triage, not a production-incident severity declaration.
- No real credentials, paid inference, engine installation, or unrelated process termination were used for review probes. Mocked observations establish the stated code behavior, not live-provider/GPU acceptance.

## Reproduction or validation

{validation}

## User impact

{impact.strip()}

## Proposed approach

{proposed.strip()}

## Acceptance criteria

""" + "\n".join(f"- [ ] {criterion}" for criterion in criteria)
        extra = EXTRA_SOURCES.get(finding, [])
        if extra:
            body += "\n\n## Additional source references\n\n" + "\n".join(f"- [{path}{':' + str(line) if line else ''}]({source_url(path, line)})" for path, line in extra)
        if finding in RELATED:
            related, explanation = RELATED[finding]
            body += f"\n\n## Related work\n\nRelated closed issue: #{related}. {explanation}"
        if finding == 23:
            body += "\n\n## Browser evidence\n\nThe first attachment shows the incorrect size. The second is the actual 640 x 360 PNG fixture.\n\n![Upscale dialog reports a 640 x 360 import as 512 x 512](./upscale-wrong-dimensions.jpg)\n\n![The original 640 x 360 fixture](./landscape-fixture.png)"
        body += "\n\n## Verification scope\n\nReal GPU inference, paid-provider compatibility, and a clean-machine packaged desktop journey remain unverified. Any follow-up implementation should target `dev` under the repository's contribution/branching rules.\n"
        assert "D:/" not in body and "C:/" not in body and "D:\\" not in body
        path = OUT / f"F{finding:02}.md"
        path.write_text(body, encoding="utf-8")
        manifest.append({"finding": f"F{finding:02}", "title": title, "labels": labels, "priority": "P1" if finding <= 19 else "P2", "evidence": evidence_label, "body_file": str(path)})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "tracker.md").write_text(f"""<!-- berry-review:2026-10-05:tracker -->
## Purpose

Track the 2026-10-05 product and technical review of Berry AI Studio at [`{SHA[:7]}`]({BASE}/commit/{SHA}) on `dev`.

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
""", encoding="utf-8")
    print(json.dumps({"prepared": len(manifest), "directory": str(OUT), "p1": 19, "p2": 25}))


if __name__ == "__main__":
    prepare()
