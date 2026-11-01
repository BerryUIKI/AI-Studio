# Berry AI Studio: Product and Technical Review

Date: 2026-10-05  
Reviewed branch: `dev`  
Reviewed commit: `c1c5dbe` (`refactor: completely deprecate and remove Ollama runtime in favor of embedded llama.cpp (#99)`)

## Executive assessment

**The current application is a substantial development prototype, but it does not yet meet its own first-release acceptance criteria.** The creative canvas and selection-based actions are the right product direction. The repository also has useful foundations: declarative node contracts, optional engine runtimes, asset adoption, semantic hashing, TypeScript compilation, and automated tests. Those foundations are not consistently connected into a reliable user journey.

From a Product Manager's perspective, the primary problem is that setup, creation, editing, export, and reopening a project do not form a trustworthy end-to-end experience. Several controls report success without changing the underlying system. Defaults can lead users into unavailable engines. Model readiness, task progress, and diagnostics communicate more confidence than the implementation supports.

From a CTO's perspective, release blockers include credential exposure, insufficient process ownership checks, incomplete installation validation, inconsistent provider dispatch, missing engine asset/model plumbing, invalid cache reuse, and unsafe shutdown/update behavior. These can cause data loss, incorrect results, unintended provider use, or interruption of unrelated work. Feature expansion should pause until these contracts are reliable.

This review contains **44 findings: 19 P1 release blockers and 25 P2 issues**. Counts describe the findings below, not the number of individual defects or independently reproduced failures. P1 means a first-release blocker because of core functionality, security, data integrity, or lifecycle impact. P2 means a material reliability, usability, performance, or maintainability issue. No P0 production incident is claimed.

## Scope, method, and limits

Reviewed the product baseline in `docs/PRODUCT_VISION.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md`, and `docs/ROADMAP.md`, along with branching rules, frontend stores/components, backend routes/runners/storage/runtime, Rust lifecycle code, packaging scripts, CI, and release-verification claims.

The checkout was clean before review and was switched to `dev`. No application implementation was changed and no commit was made. The branch's local tracking state was current; this review did not fetch or audit newer remote commits.

Evidence labels:

- **Reproduced:** observed through the browser or an isolated executable probe with disposable data.
- **Code:** the behavior follows from the reviewed implementation; a complete live integration was not executed.
- **Risk:** a design or integration concern requiring further validation before claiming an observed failure.

The browser review served the built frontend from a backend running with repository-local disposable data and engine directories. It exercised navigation, configuration, canvas creation/reload, image import, and the upscale dialog. No real user credentials were inspected, no paid inference was submitted, no local engine was installed, and no unrelated process was stopped. The browser viewport was approximately 1060 x 612; native desktop behavior and its minimum 1024 x 700 layout were not fully exercised.

### Automated checks

| Check | Result |
| --- | --- |
| Backend pytest | 157 passed; one Starlette/httpx deprecation warning |
| Frontend tests | 41 passed across 9 test files |
| Frontend production build | Passed; JavaScript chunk 645.91 kB, 184.78 kB gzip; bundle-size and mixed static/dynamic import warnings |
| Frontend lint | Passed with 2 `no-empty` warnings |
| Rust launcher tests | 3 passed |
| Tauri Rust `cargo check --locked` | Passed |

Passing these checks establishes the current automated baseline. It does not establish successful real-engine inference, paid-provider compatibility, clean-machine distribution, or the PRD's complete user journeys.

Executable evidence is saved in [review-probes.py](D:/dev/AI-Studio/docs/reviews/2026-10-05-evidence/review-probes.py) and [probe-results.json](D:/dev/AI-Studio/docs/reviews/2026-10-05-evidence/probe-results.json). Probes mock provider calls, downloads, installation work, and process termination; their output must not be interpreted as live integration coverage. Run the script from the repository with `backend/.venv/Scripts/python.exe`; it writes disposable fixtures under `.review-runtime`.

## P1 findings: address before release

### F01. Secrets are stored in plaintext and the LLM configuration API returns the raw key

**Evidence: Reproduced.** [credentials.py:59](D:/dev/AI-Studio/backend/app/runtime/credentials.py:59) writes the complete credential dictionary to JSON. [main.py:883](D:/dev/AI-Studio/backend/app/main.py:883) returns an `LLMConfig` containing `api_key` without authentication. A disposable key was recovered both from the saved file and the GET response. Catching write failures also allows a setting operation to appear successful without durable storage.

**Impact:** a local client can retrieve an API credential; UI assurances about protected storage overstate the implementation. **Acceptance:** use OS-backed secret storage where supported, return redacted/write-only secret fields, and surface save failures. Verify no API response, log, export, or project serialization contains a complete key.

### F02. Sensitive localhost routes and the execution WebSocket lack a session/origin boundary

**Evidence: Reproduced + Code.** A simple cross-origin POST reached the runtime-start handler, and an arbitrary-origin WebSocket was accepted at [main.py:1098](D:/dev/AI-Studio/backend/app/main.py:1098). There is no application session authentication for execution or lifecycle mutations. A restrictive CORS response policy does not itself authorize requests or prevent every mutation.

**Impact:** an untrusted client that can reach the service can trigger execution or lifecycle actions. Browser private-network restrictions may constrain a particular web attack; the probe does not claim a complete browser exploit. **Acceptance:** require a per-launch session credential, validate origins on browser-facing writes and WebSocket handshakes, and test unauthorized install, stop, shutdown, execution, and secret reads.

### F03. A recycled PID can be mistaken for an owned engine process

**Evidence: Reproduced.** [supervisor.py:65](D:/dev/AI-Studio/backend/app/runtime/supervisor.py:65) and [webui_supervisor.py:67](D:/dev/AI-Studio/backend/app/runtime/webui_supervisor.py:67) accept a Windows executable name containing `python` as ownership evidence. Both accepted the probe's unrelated Python process. Stop subsequently uses `taskkill /F /T`.

**Impact:** a stale PID file can cause Berry to stop an unrelated Python process and its children, contrary to the external-process ownership requirement. **Acceptance:** verify executable path, command line/runtime identity, creation time, and ownership metadata before any termination; treat ambiguity as unowned. Test recycled PIDs without killing a real process.

### F04. The canvas is not a durable project

**Evidence: Reproduced + Code.** A text item disappeared after browser reload. [useCanvasStore.ts:48](D:/dev/AI-Studio/frontend/src/stores/useCanvasStore.ts:48) initializes an in-memory canvas, and the frontend does not connect this state to the backend project CRUD API. Database project tests exercise storage primitives rather than saving and reopening the actual application canvas.

**Impact:** users can lose layout, selections, relationships, and their working context on restart. This directly fails R15. **Acceptance:** create/open/save/autosave a versioned project containing canvas layout, asset references, lineage, and generation history. Test restart recovery and missing-file handling through the UI.

### F05. Imported images are not transferred into ComfyUI's input directory

**Evidence: Code.** [creative_runner.py:364](D:/dev/AI-Studio/backend/app/runners/creative_runner.py:364) supplies only a Berry-managed asset basename to `LoadImage`; the same pattern is used for masks, upscaling, and image-to-video. [supervisor.py:169](D:/dev/AI-Studio/backend/app/runtime/supervisor.py:169) launches ComfyUI with a separate `engine/input` directory. No upload/copy bridge connects those locations.

**Impact:** selection-based local editing can reference a file the engine cannot load. ComfyUI validates input filenames against its input directory. [ComfyUI LoadImage implementation](https://github.com/Comfy-Org/ComfyUI/blob/master/nodes.py).

**Acceptance:** transfer source and mask assets through the engine's upload contract, retain the returned engine filename, and verify import -> img2img/inpaint/upscale with a real managed engine and an external engine.

### F06. The painted inpainting mask has opposite semantics in ComfyUI

**Evidence: Code, checked against upstream semantics.** The mask canvas paints opaque white over an otherwise transparent mask. [macro_compiler.py:221](D:/dev/AI-Studio/backend/app/runners/macro_compiler.py:221) uses `LoadImage`'s MASK output, which ComfyUI computes as `1 - alpha`. Painted pixels therefore become zero in that mask while unpainted transparent pixels become one. [ComfyUI LoadImage implementation](https://github.com/Comfy-Org/ComfyUI/blob/master/nodes.py).

**Impact:** the area the user marks for editing can be protected while the surrounding area is selected. WebUI's grayscale mask and OpenAI's alpha conventions also require explicit adapters. **Acceptance:** define one canonical mask meaning, convert it per provider, and test a small known painted region against real outputs, preserving source/mask alignment.

### F07. Downloaded model locations are not connected to engine search paths

**Evidence: Code.** [model_downloader.py:211](D:/dev/AI-Studio/backend/app/runtime/model_downloader.py:211) places ComfyUI models in the shared `engine/models` tree, but the ComfyUI launch command supplies no corresponding extra-model-path configuration. WebUI download paths use `Path.home()/.ai-workflow/engine/webui/models`, whereas the managed supervisor supplies directories under its configured engine root. Custom scan roots only index files.

**Impact:** a successful download or model scan does not guarantee that the chosen engine can load the model. **Acceptance:** centralize path resolution; configure ComfyUI shared paths and WebUI model directories from the same registry; confirm a newly downloaded model appears in engine discovery and completes inference without manual relocation.

### F08. Managed WebUI launch flags conflict with the intended deployment and native UI

**Evidence: Code.** [webui_supervisor.py:169](D:/dev/AI-Studio/backend/app/runtime/webui_supervisor.py:169) passes `--listen 127.0.0.1` and `--nowebui`. Upstream defines `--listen` as a boolean flag, with `--server-name` as a separate address option; `--nowebui` disables the native interface. [Official WebUI arguments](https://github.com/AUTOMATIC1111/stable-diffusion-webui/blob/master/modules/cmd_args.py).

The installer also creates a venv from Berry's interpreter. This checkout uses Python 3.14, while upstream's Windows launcher checks for Python 3.10 and identifies 3.10.6 as its tested version. [Official launch checks](https://github.com/AUTOMATIC1111/stable-diffusion-webui/blob/master/modules/launch_utils.py).

**Impact:** launch incompatibility, unintended listener configuration, and an unavailable native UI are credible integration blockers. A GPU installation was not attempted. **Acceptance:** select a supported isolated interpreter and pinned engine version, use correct loopback flags, and verify both API health and native UI access.

### F09. WebUI ignores the model selected by the user

**Evidence: Reproduced.** [webui_runner.py:52](D:/dev/AI-Studio/backend/app/runners/webui_runner.py:52) builds a txt2img payload without `sd_model_checkpoint` or an appropriate override. A request for `chosen-checkpoint.safetensors` produced no model-selection field. Other image-generation payloads likewise do not establish the selected checkpoint.

**Impact:** the engine can use its previously loaded model while Berry records and caches the user's requested model as if it were used. **Acceptance:** validate and apply the selected model through WebUI's supported contract; record the effective engine/model identity and test two distinct checkpoints.

### F10. Provider resolution and actual cloud dispatch disagree

**Evidence: Reproduced.** For `engine_id=fal_ai`, `model=sdxl-turbo`, the hash/provider resolver selected Fal, but [creative_runner.py:627](D:/dev/AI-Studio/backend/app/runners/creative_runner.py:627) dispatched to SiliconFlow when both dummy keys were available. The resolver and executor contain separate heuristic decision trees.

**Impact:** the selected provider, actual service, credential use, cache identity, and provenance can diverge. This also affects users' expectations about cost and asset destination. **Acceptance:** resolve a single capability-checked execution plan before submission and use it for validation, dispatch, hashing, UI disclosure, and provenance. Reject unsupported combinations rather than silently switching providers.

### F11. Cache hits report success even when the output file is missing

**Evidence: Reproduced.** After generating a disposable asset and deleting its file, the identical request returned `success=true`, `is_cached=true`, and the old asset URL; the runner was called only once. [creative_runner.py:211](D:/dev/AI-Studio/backend/app/runners/creative_runner.py:211) trusts [cache.py:120](D:/dev/AI-Studio/backend/app/core/cache.py:120) without checking output availability.

**Impact:** users see a successful result that cannot be displayed or exported; R09 and R16 require valid output reuse. **Acceptance:** validate cache output references and files, invalidate broken entries, and recompute or report an actionable missing-output state. Add startup reconciliation and tests for deleted/corrupt assets.

### F12. Installation can report completion for an empty engine and polling marks active installs interrupted

**Evidence: Reproduced.** An existing empty ComfyUI directory, with mocked venv creation, was reported `completed` despite having no `main.py`. [installer.py:161](D:/dev/AI-Studio/backend/app/runtime/installer.py:161) skips cloning for any existing destination, and missing prerequisites can bypass dependency setup. Separately, [installer.py:56](D:/dev/AI-Studio/backend/app/runtime/installer.py:56) changes an in-progress manifest to `interrupted` whenever it is read, including ordinary live status polling.

**Impact:** installed state is unreliable, retry can preserve broken directories, and the UI can misreport an installation while it is still running. **Acceptance:** distinguish an active worker from a previous interrupted attempt, lock operations per engine, install into staging, and mark completion only after entrypoint, dependency, and smoke-health validation.

### F13. Model downloads ignore declared integrity metadata

**Evidence: Reproduced.** A fixture declared a 100-byte model and an explicit SHA-256; a 13-byte corrupt response was still marked `completed`. [model_downloader.py:171](D:/dev/AI-Studio/backend/app/runtime/model_downloader.py:171) promotes the partial file without validating the catalog checksum or expected size. Replacing a previous destination first unlinks it.

**Impact:** truncated or incorrect models can be offered as usable; replacement can discard a working file before promotion succeeds. Resume/fallback also needs Content-Range and source-identity validation. **Acceptance:** verify length and checksum where available, reject invalid resumptions, and atomically replace only validated artifacts while preserving the previous version on failure.

### F14. Engine update protection excludes creative tasks and rollback does not restore the environment

**Evidence: Reproduced + Code.** [main.py:449](D:/dev/AI-Studio/backend/app/main.py:449) checks only workflow cancellations. A running creative task did not activate the update guard. The check is also captured as a snapshot. [installer.py:340](D:/dev/AI-Studio/backend/app/runtime/installer.py:340) rolls source back with `git checkout` after dependency mutation, leaving the venv changed and potentially the repository detached.

**Impact:** an engine can be updated during ordinary canvas generation, and a reported rollback can leave a mismatched runtime. **Acceptance:** use one task/lifecycle registry and an exclusive update lease; stage a complete new runtime, validate it, and switch atomically. Roll back both code and dependencies.

### F15. Desktop shutdown bypasses the backend's active-task refusal and contradicts Keep Running

**Evidence: Code.** [backend.rs:177](D:/dev/AI-Studio/frontend/src-tauri/src/backend.rs:177) posts `force=false`, ignores the response, waits 500 ms, then kills its child. [App.tsx:190](D:/dev/AI-Studio/frontend/src/App.tsx:190) uses the same native close path for Keep Running. Native close/destruction calls backend shutdown regardless of that choice. The shutdown helper also sends a request when no child is owned.

**Impact:** active work can be interrupted after a graceful-shutdown refusal; closing can stop a pre-existing backend or defeat the promised exit policy. **Acceptance:** define explicit keep-running/stop-owned/force modes, respect refusals, wait for acknowledged safe shutdown, and never shut down an unowned service. Test titlebar close, Alt+F4, destroy, and active tasks.

### F16. WebSocket reconnect can resubmit work and stale events are not isolated

**Evidence: Code.** [useCanvasStore.ts:430](D:/dev/AI-Studio/frontend/src/stores/useCanvasStore.ts:430) sends the full run payload on every new connection. The backend has no durable run-id deduplication, and the frontend does not consistently reject events from obsolete runs. Heartbeats are sent even though the server does not continue reading them after the initial request.

**Impact:** a transport failure can initiate duplicate inference or charges; a late event can overwrite a newer run's state. This was not reproduced with a paid service. **Acceptance:** separate submission from subscription, persist an idempotency key, resume an existing run, check run identity on every event, and implement or remove the heartbeat contract.

### F17. Missing runners produce node errors but the graph still finishes completed

**Evidence: Reproduced.** An unknown probe node type with no runner emitted an error and ended with `GRAPH_FINISHED.status=completed`. [main.py:1196](D:/dev/AI-Studio/backend/app/main.py:1196) continues after the missing-runner branch, allowing the loop's completion path. Execution validation also lacks a complete required-port/type/edge contract.

**Impact:** success is reported for a failed graph, and unsupported workflows reach execution before useful validation. **Acceptance:** preflight every node, runner, required input, port type, and reference; derive final status from all node outcomes and block dependents consistently.

### F18. Release packaging does not establish a self-contained clean-machine application

**Evidence: Code + Risk.** [package-windows-release.ps1:96](D:/dev/AI-Studio/scripts/package-windows-release.ps1:96) copies a development venv's executable, site-packages, and original `pyvenv.cfg`; it does not provision the complete base Python distribution that the venv references. It still emits a package when the venv is absent. The script builds the Tauri binary before building the frontend, creating missing/stale-asset risk. Engine installation requires Git without establishing a bundled/provisioned prerequisite.

**Impact:** source-machine checks can pass while a recipient cannot start Berry or install engines. An additional isolated probe copied the venv executable and configuration and confirmed that its `sys.base_prefix` still points outside the copied runtime. [Packaging probe result](D:/dev/AI-Studio/docs/reviews/2026-10-05-evidence/packaging-probe-result.json). This demonstrates base-runtime dependence; a clean VM failure is not claimed because that test was not run. **Acceptance:** package a pinned redistributable runtime, build frontend before embedding it, fail incomplete builds, and run launch/onboarding/inference/exit on a Windows VM with no Python, Git, or development tools.

### F19. Image upload accepts unrestricted active content and unbounded payloads

**Evidence: Code.** [main.py:769](D:/dev/AI-Studio/backend/app/main.py:769) reads the entire upload without a size limit or image decoder check, accepts arbitrary media types, and [main.py:1020](D:/dev/AI-Studio/backend/app/main.py:1020) serves files inline based on filename MIME inference. Base64 upload has similar validation gaps. Tauri CSP is disabled.

**Impact:** large inputs can exhaust memory, invalid images enter the asset library, and uploaded HTML/SVG can become same-origin active content if opened. No malicious script was executed. **Acceptance:** enforce byte/pixel limits, validate and normalize supported media, prevent executable content from being served with application-origin privileges, and set explicit content/security headers.

## P2 findings: reliability, usability, efficiency, and maintainability

### F20. Task and generation history are not durable

**Evidence: Reproduced + Code.** The probe executed a creative request, but SQLite `runs` and `tasks` remained empty. Those tables exist in [db.py:87](D:/dev/AI-Studio/backend/app/storage/db.py:87), while active execution state lives in dictionaries. Download workers are also memory-only.

**Impact:** restart loses task status, retry context, cancellation targets, and recovery information; a remote job can outlive its local record. **Acceptance:** persist task transitions, provider job IDs, effective parameters, errors, outputs, and ownership; reconcile interrupted work on startup and expose a usable history/task panel.

### F21. Cancellation is not available early enough in the primary creative workflow

**Evidence: Code.** The creative POST waits for execution before returning its task ID. The frontend cannot use that ID to cancel while waiting. [creative_runner.py:147](D:/dev/AI-Studio/backend/app/runners/creative_runner.py:147) signals an event but checks it after awaited execution; it can return `cancelled` while a cloud job continues. Comfy interrupt is not scoped to an individual queued task.

**Impact:** a user cannot reliably stop a long operation, and task state can overstate cancellation. **Acceptance:** return an ID at submission, stream state independently, distinguish cancel-requested from confirmed cancellation, disclose unsupported remote cancellation, and add bounded concurrency/queue ownership.

### F22. Planning, hashing, and execution do not share a single cache contract

**Evidence: Code.** The plan endpoint hashes upstream computation state and checks an in-memory cache, while execution uses output-derived hashes and persistent lookup. [cache.py:16](D:/dev/AI-Studio/backend/app/core/cache.py:16) hashes a string image URL as a string rather than using verified image bytes. Model identity generally comes from a name; the runner version defaults to a constant, and endpoint/runtime revisions are not fully represented.

**Impact:** plans can disagree with actual reuse; same-name model replacement or changed content behind a stable URL can yield invalid reuse. **Acceptance:** use one canonical execution plan, port-aware content identities, effective model/runtime revisions, persistent valid-output lookup, and explicit Reuse/New Variation semantics.

### F23. Image dimensions are guessed and upscale semantics are inconsistent

**Evidence: Reproduced + Code.** Importing the [640 x 360 fixture](D:/dev/AI-Studio/docs/reviews/2026-10-05-evidence/landscape-fixture.png) displayed 512 x 512 and a 1024 x 1024 2x target. [useCreativeStore.ts:287](D:/dev/AI-Studio/frontend/src/stores/useCreativeStore.ts:287) supplies 512 defaults because stored dimensions are absent. [creative_runner.py:185](D:/dev/AI-Studio/backend/app/runners/creative_runner.py:185) overwrites dimensions from aspect ratio for all actions. The Comfy upscale graph uses the model's native scale rather than applying the chosen factor, and the result metadata uses requested dimensions.

**Impact:** the preview, requested size, actual result, and export metadata can disagree. **Acceptance:** decode actual dimensions on adoption, preserve source ratio, implement requested scaling explicitly, and derive result metadata from the output.

![A 640 x 360 imported fixture is shown as 512 x 512 in the upscale dialog](D:/dev/AI-Studio/docs/reviews/2026-10-05-evidence/upscale-wrong-dimensions.jpg)

### F24. Undo/redo does not represent a complete canvas transaction

**Evidence: Code.** [useCanvasStore.ts:56](D:/dev/AI-Studio/frontend/src/stores/useCanvasStore.ts:56) snapshots only nodes. Removing nodes also changes edges, but undo does not restore those edges. Position updates and some imported/generated insertions bypass the same snapshot path.

**Impact:** undo can produce a different graph or cannot reverse the action the user just took. **Acceptance:** define transactions for movement, grouping, imports, generation insertion, deletion, and connections; restore nodes, edges, selection, and affected relationships together.

### F25. Engine configuration shows success without saving

**Evidence: Reproduced + Code.** [EngineConfigModal.tsx:37](D:/dev/AI-Studio/frontend/src/components/launcher/EngineConfigModal.tsx:37) invokes an optional save callback, then unconditionally shows success. [App.tsx:438](D:/dev/AI-Studio/frontend/src/App.tsx:438) supplies no save handler. Port state initializes before an instance is selected and does not synchronize; WebUI was shown as port 8188.

**Impact:** users believe changed ports/arguments will take effect, causing failed connections and confusing retries. **Acceptance:** load the selected instance configuration, persist through a real backend operation, show pending/error/success from its result, and verify restart behavior.

### F26. The managed Uninstall action only stops the engine

**Evidence: Code.** [App.tsx:83](D:/dev/AI-Studio/frontend/src/App.tsx:83) unbinds external engines but routes managed Uninstall to stop rather than removing the managed installation. A folder action in embedded views also routes to management rather than opening the advertised directory.

**Impact:** labels promise storage and lifecycle changes that do not happen. **Acceptance:** separate Stop, Remove Connection, Open Folder, and Uninstall; implement each contract and explain retained models/assets before an uninstall.

### F27. External engine identity and endpoints are not consistently used for execution

**Evidence: Code.** Creative runners use default ComfyUI/WebUI clients instead of resolving the chosen registry connection. Frontend lifecycle dispatch often chooses by engine type rather than managed/external identity. [EmbeddedEngineView.tsx:29](D:/dev/AI-Studio/frontend/src/components/engine/EmbeddedEngineView.tsx:29) reconstructs a localhost URL from a port, ignoring the configured host, protocol, and path. Both WebUI start callbacks in App use the Comfy runtime toggle.

**Impact:** the visible connection can differ from the engine receiving work or a start request. **Acceptance:** carry one stable connection ID end to end; use its endpoint, capabilities, ownership, and lifecycle policy without type-based fallback.

### F28. Model roots, external connections, and mirror preferences do not survive restart

**Evidence: Reproduced + Code.** Reconstructing [ModelStore](D:/dev/AI-Studio/backend/app/storage/model_store.py:136) lost a custom root. Connections and mirror configuration are also in-memory. The install path does not consume the mirror URL transformation/PyPI helper, and deployment handlers do not carry the selected mirror through to installation.

**Impact:** setup has to be repeated, and mirror selection can create a false expectation of faster/reliable downloads. **Acceptance:** persist configuration with stable IDs, read it at startup, and demonstrate that the selected mirror actually controls Git, Python-package, and model download requests where advertised.

### F29. Unknown and invalid model files are marked ready and compatible

**Evidence: Reproduced.** A fake `.gguf` containing `not-a-real-model` was marked ready with unknown architecture and ComfyUI compatibility. [model_store.py:195](D:/dev/AI-Studio/backend/app/storage/model_store.py:195) starts every record as ComfyUI-compatible and determines readiness from an empty dependency list. FLUX dependencies are declared missing without checking the inventory or bundled components.

**Impact:** users choose models that cannot run, while valid bundles may look incomplete. **Acceptance:** separate recognized format, integrity, architecture, dependency presence, and engine-tested compatibility. Preserve unknown states, resolve dependency sets, and use content/revision identity rather than path plus size alone.

### F30. Model Hub is not connected to installation state or a usable selection workflow

**Evidence: Code + Browser.** Catalog installed state is not reconciled with local inventory; completed downloads do not establish a selected canvas model. The default Use Cloud handler only logs to the console. Engine targeting is limited, and there is no LLM category tab despite LLM entries. [hardware_evaluator.py:83](D:/dev/AI-Studio/backend/app/runtime/hardware_evaluator.py:83) evaluates total rather than available VRAM and shows fixed speed bands such as `<1s` without workload/device benchmarking.

**Impact:** discovery, installation, readiness, and use feel like disconnected screens; performance promises may be misleading. **Acceptance:** refresh inventory after download, show actual installed/readiness state, support Use Model/Use Provider with validated capabilities, and label estimates with their assumptions.

### F31. First-use defaults do not guide a user to a successful first image

**Evidence: Browser + Code.** The empty canvas lacks a clear guided first task. Generate remains available with an uninstalled default engine; model selection exposes a filename field. Cloud is represented as a generic execution choice even though providers support different actions and parameters.

**Impact:** a new user reaches a technical failure before understanding the setup choice. **Acceptance:** offer an obvious cloud/local setup path, a validated model/provider picker, readiness checks with a direct repair action, capability-specific controls, and a short default prompt that can produce a first result without node wiring.

### F32. Product scope and information hierarchy are ahead of the verified image workflow

**Evidence: Product assessment.** Video, Agent, node-oriented execution, native engine views, model management, and installation all compete in primary navigation while first-release image acceptance remains incomplete. The approved baseline emphasizes image creation and durable creative projects; later-feature surfaces increase the number of combinations users can enter.

**Impact:** onboarding burden, testing scope, and maintenance grow faster than the core workflow's reliability. **Acceptance:** make the primary journey project -> create/import -> select/edit -> export; place engine internals and experimental features behind secondary navigation and explicit availability states until their contracts are verified.

### F33. Progress and engine diagnostics are not truthful observations

**Evidence: Code + Browser.** [useCreativeStore.ts:163](D:/dev/AI-Studio/frontend/src/stores/useCreativeStore.ts:163) advances a timer and displays checkpoint/latent/VAE stages independently of engine events, including cloud runs. [engine_manager.py:396](D:/dev/AI-Studio/backend/app/runtime/engine_manager.py:396) returns invented ready/verified log lines when supervisors cannot supply logs. Supervisor stdout/stderr goes to `DEVNULL`; PID existence can be displayed as running without service health.

**Impact:** a hung or failed engine looks active and support loses the real error. Low-level latent/VAE terminology also violates the intended high-level experience. **Acceptance:** use observed phases or an honest indeterminate state, retain bounded real logs with redaction, distinguish starting/running/healthy, and show actionable errors.

### F34. Agent chat displays continuity without sending conversation identity

**Evidence: Code.** [AgentPanel.tsx:84](D:/dev/AI-Studio/frontend/src/components/agent/AgentPanel.tsx:84) sends the new message and selected asset but not the returned conversation ID. Backend chat therefore creates a fresh conversation for subsequent messages. Panel state is transient, backend conversation storage is unbounded, and inserted proposal outputs use fixed canvas coordinates.

**Impact:** follow-up requests can lose context despite visible chat history; repeated results can overlap. **Acceptance:** persist/resend conversation identity, define retention limits, tie proposals to the active project and task lifecycle, and position accepted outputs relative to the relevant selection.

### F35. Embedded LLM lifecycle has incomplete success and readiness contracts

**Evidence: Reproduced + Code.** A mocked successful `LlamaServerSupervisor.stop()` returned `None`, despite its dictionary return annotation. [main.py:152](D:/dev/AI-Studio/backend/app/main.py:152) automatically starts the first available local model at backend startup. The runtime uses a fixed port and starts without awaiting service readiness; local-provider configuration can appear ready before installation/health is established.

**Impact:** stop callers cannot rely on a result, startup can unexpectedly consume resources, and the Agent can appear available while its service is unavailable. **Acceptance:** return explicit lifecycle results, honor a saved opt-in/start preference, select a known model, check port ownership, and report health separately from installation and PID state.

### F36. Export naming and media rendering can disagree with actual content

**Evidence: Code.** Image export actions commonly force a `.png` filename rather than converting or retaining the actual format. Explicit `.webp`/`.gif` URLs are handled as images, but Berry returns extensionless managed-asset URLs; a video-tagged animated WebP at such a URL follows the HTML video branch. Cloud source encoding also assumes an image MIME type rather than the decoded format.

**Impact:** exported files have misleading extensions, some generated media cannot preview, and provider input validation may fail. **Acceptance:** track verified MIME/codec/extension, render animated images versus playable video appropriately, and either export original content correctly or perform an explicit conversion.

### F37. GUI density and visual feedback need a focused usability pass

**Evidence: Browser; qualitative assessment.** The dark visual system is reasonably consistent, but titlebar/action text is small, advanced controls dominate the canvas at the tested viewport, and the dock/minimap compete for space. Model cards retain large empty preview areas when remote thumbnails fail. Important state is spread across the toolbar, sidebar, settings, hub, and modal dialogs.

**Impact:** users spend attention finding status/configuration rather than reviewing creative results. **Acceptance:** establish one primary action, progressive disclosure for advanced controls, reliable thumbnail fallbacks, a clear task/status area, and test native minimum size, 125%/150% display scaling, and common laptop sizes. The screenshot alone does not establish failure at the native minimum height.

### F38. Dialog and keyboard accessibility is incomplete

**Evidence: Browser + Code.** Several modal implementations lack consistent dialog semantics, focus trapping/restoration, and Escape handling. Icon-only controls have incomplete accessible names, clickable model cards are not consistently keyboard-operable, and labels are not always associated with inputs. Hidden mounted canvas views retain global keyboard handlers that do not cover all editable/focusable contexts.

**Impact:** keyboard/screen-reader users struggle to operate the app, and shortcuts can affect the canvas from another view. **Acceptance:** standardize accessible modal/control primitives, scope shortcuts to the active view and focus context, and test keyboard-only creation, editing, cancel, export, and navigation.

### F39. Language selection advertises broader coverage than the UI provides

**Evidence: Browser + Code.** Settings lists multiple languages, but important canvas/dialog/error text is hardcoded in English and some launcher/model badges remain Chinese. Date, number, and error formatting are not governed by one locale contract.

**Impact:** switching language produces a mixed interface and makes support instructions harder to follow. **Acceptance:** advertise only supported coverage, move product-facing strings to one translation system, provide fallbacks, and validate the complete primary workflow per offered locale.

### F40. Blocking work runs on asynchronous request paths

**Evidence: Code.** Manager/model endpoints call synchronous directory scanning and hardware evaluation; hardware inspection uses subprocesses. Lifecycle operations use synchronous process calls, while async asset methods perform synchronous file writes/hashing. [main.py:236](D:/dev/AI-Studio/backend/app/main.py:236) rescans inventory for status.

**Impact:** large libraries or slow disks/processes can delay unrelated health, task, and UI requests. No load benchmark was run. **Acceptance:** move blocking work to bounded worker threads/processes, maintain an incremental model index, cache hardware/status snapshots, and measure request latency during large imports/scans.

### F41. Frontend subscriptions, polling, and eager mounting do unnecessary work

**Evidence: Code + Build.** App and multiple canvas components subscribe to entire Zustand stores, so timer/progress changes can rerender unrelated UI. [ViewContainer.tsx:19](D:/dev/AI-Studio/frontend/src/components/navigation/ViewContainer.tsx:19) mounts every view and merely hides inactive ones, retaining effects/listeners. Independent status polling and full node snapshots add overhead. The production bundle contains a 645.91 kB JavaScript chunk.

**Impact:** idle work and update costs grow with the canvas, even when another view is open. **Acceptance:** use selectors, suspend inactive effects, lazy-load secondary views, share polling, and profile a realistic large canvas before choosing additional optimizations. Bundle size alone is not a measured startup failure.

### F42. Execution and lifecycle rules are duplicated across large, tightly coupled modules

**Evidence: Code.** `main.py` combines API composition, globals, orchestration, caching, cancellation, runtime management, assets, models, and Agent routes. Provider resolution/dispatch is duplicated; cancellation routes and Rust backend lifecycle implementations overlap. Engine identifiers and response contracts differ across layers. Repository rules against unrestricted `any`, arbitrary inline styles, and missing Python typing are not consistently enforced.

**Impact:** a behavior change can fix one entry point while another retains the defect; integration contracts are hard to review. **Acceptance:** extract typed service boundaries for execution plans, durable tasks, engine connections/lifecycle, and assets; retain thin routes, generate/share API contracts where practical, and enforce targeted static checks. Refactor separately from behavioral fixes.

### F43. Test and release claims exceed the evidence actually established

**Evidence: Code + Validation.** All checks in this review passed, yet the reproduced issues above are outside their assertions. Frontend tests focus on stores/helpers rather than complete rendered workflows. The release-verification report marks R01-R18 verified using a mix of mocks, storage-unit tests, source inspection, and build success; that does not establish complete current-head acceptance. CI does not establish a packaged clean-machine desktop user journey.

**Impact:** regression gates can remain green while a release-critical workflow is broken. **Acceptance:** map every requirement to an end-to-end assertion and evidence level; record the tested commit, environment, provider/engine versions, and output artifacts. Gate release on persistence, first image, masked edit, upscale/export, external ownership, interrupted install/update, and safe exit.

### F44. Native capability and security configuration require production-path verification

**Evidence: Risk.** The native window navigates to an HTTP backend origin, while [capabilities/default.json](D:/dev/AI-Studio/frontend/src-tauri/capabilities/default.json) declares window permissions without a remote URL scope. Tauri's capability documentation requires explicit remote configuration for remote sources. [Official Tauri capability documentation](https://v2.tauri.app/security/capabilities/). [tauri.conf.json](D:/dev/AI-Studio/frontend/src-tauri/tauri.conf.json) also disables CSP.

**Impact:** production-origin native commands may not have the intended permissions, while document/content security is too permissive. This was not tested in the native application and is not asserted as an observed broken button. **Acceptance:** test the packaged production origin, grant narrowly scoped capabilities to the intended local origin, add an appropriate CSP, and verify window controls plus untrusted-content isolation.

## First-release acceptance assessment

These statuses refer to current-head evidence from this review. They do not invalidate every historical test result; they identify gaps between primitive tests and user acceptance.

| Requirement | Assessment | Principal findings |
| --- | --- | --- |
| R01 Lightweight startup/onboarding | Partial; core is optional-engine oriented, onboarding and automatic LLM startup need work | F31, F35, F41 |
| R02 Device readiness | Partial; hardware data exists, estimates and prerequisites are incomplete | F08, F18, F30 |
| R03 Managed installation | Blocked | F08, F12, F28 |
| R04 Existing connection | Partial; registry exists, identity is not carried through | F03, F27, F28 |
| R05 Engine lifecycle | Blocked | F03, F14, F15, F33, F35 |
| R06 Infinite canvas | Partial; selection workflow exists, durability/undo/accessibility incomplete | F04, F24, F38 |
| R07 Image creation | Blocked across promised combinations | F05, F07, F09, F10, F31 |
| R08 Inpainting | Blocked for managed ComfyUI plumbing/mask semantics | F05, F06 |
| R09 Upscaling/export | Partial with correctness defects | F05, F11, F23, F36 |
| R10 Workflow templates | Partial; compilation is not full runtime preflight | F07, F17, F29 |
| R11 Model inventory | Blocked on truthful readiness/compatibility | F13, F29, F30 |
| R12 Directory management | Partial; non-destructive indexing exists, persistence/path sharing missing | F07, F28 |
| R13 BYOK cloud | Blocked on secrets and provider contract | F01, F02, F10 |
| R14 Task lifecycle | Blocked | F14-F17, F20, F21, F33 |
| R15 Persistence | Blocked at actual application level | F04, F20, F28 |
| R16 Reuse/variants | Partial; hashing foundation exists, valid reuse is not assured | F10, F11, F22 |
| R17 Portable architecture | Partial; clean-machine packaging and platform runtime evidence missing | F08, F18, F40, F43 |
| R18 Native entry points | Partial; WebUI flags/callbacks and production capabilities need correction/validation | F08, F27, F44 |

## Recommended delivery sequence

1. **Protect data and ownership.** Address secrets/session boundaries, safe media serving, process identity, and shutdown/update refusal handling (F01-F03, F14-F15, F19). Establish durable project/task foundations (F04, F20) before users entrust ongoing work to the app.
2. **Complete one real image journey.** Resolve execution identity once, connect model/input paths, normalize masks/dimensions, enforce valid cache outputs, and verify provider/model selection (F05-F11, F17, F22-F23). Start with one supported cloud provider and one pinned managed local engine, then extend using the same contracts.
3. **Make setup and recovery honest.** Validate/stage installation and downloads, persist configuration, repair misleading controls and logs, and prove the clean-machine package (F12-F13, F18, F25-F30, F33, F35, F44).
4. **Reduce product friction and maintenance cost.** Finish undo, export, onboarding, accessibility, localization, active-view behavior, and performance profiling. Consolidate duplicated service contracts and release evidence (F24, F31-F32, F34, F36-F43).

For PM ownership, prioritize successful first-image rate, successful reopen rate, edit/export completion rate, and recovery clarity. For CTO ownership, prioritize correctness of execution identity, zero termination of unowned processes, durable task transitions, validated artifact promotion, and packaged clean-machine acceptance. Measure these with real workflows; do not substitute feature count or unit-test count for acceptance.

## Suggested release gates

- A new user on a clean Windows machine reaches a first cloud image without local engine dependencies.
- A project with imported/generated assets, positions, lineage, and history reopens correctly after process restart.
- A pinned managed engine supports txt2img, imported img2img, known-region inpainting, requested-factor upscale, and correctly formatted export.
- A selected provider/model is the actual provider/model used and recorded; repeated unchanged execution reuses an available output, and an explicit variation generates new output.
- Disconnect/reconnect does not resubmit a paid job; cancellation and retry preserve accurate, durable states.
- Interrupted downloads/installations/updates remain incomplete and recover without damaging prior working artifacts or models.
- Stop, update, and exit never terminate an unowned process; active-task refusals and Keep Running are respected.
- No raw key is returned or exported; unauthorized local-origin requests and unsafe uploaded content cannot invoke privileged application behavior.
- The packaged native production path passes these journeys with no development-tool prerequisites and correct window/capability behavior.

The immediate recommendation is a stabilization milestone against these gates, followed by evidence-based expansion of Video and Agent functionality.
