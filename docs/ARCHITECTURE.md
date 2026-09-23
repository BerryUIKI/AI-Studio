# Berry AI Studio Target Architecture

Date: 2026-09-23. Status: implementation specification; not a description of completed code.
Product authority: [Vision](PRODUCT_VISION.md) and [PRD](PRD.md).

## Boundaries

Retain the existing React/TypeScript, Zustand, Tailwind and FastAPI foundation where useful. Refactor incrementally rather than rewriting the prototype indiscriminately.

The Rust launcher owns Berry application bootstrap and presents the environment manager. The creative UI manages a canvas and high-level actions. The backend remains authoritative for projects, assets, model inventory, execution, secrets and managed-engine installation/runtime supervision. The launcher calls these services through a versioned local interface after bootstrap; engine and model logic must not be duplicated in Rust. Local engines and cloud providers are optional adapters. The core starts without GPU packages.

API-first means a complete cloud-only path remains available. It does not diminish the approved NVIDIA/local installation experience.

## Components

| Component | Responsibility |
| --- | --- |
| Rust launcher/manager | Berry startup, readiness, model inventory presentation, managed engine controls and update orchestration |
| Creative workspace | Canvas objects, selection, contextual actions, parameters and status |
| Project service | Versioned project documents, layout, history and recovery |
| Asset service | Managed files, content hashes, metadata and export |
| Model catalog | User roots, model identities, engine compatibility and dependencies |
| Template registry | Curated workflow versions and high-level input/output mappings |
| Task service | Immutable submissions, scheduling, state, cancellation and events |
| Execution adapters | ComfyUI, WebUI and BYOK cloud capabilities and calls |
| Runtime service | Installations, readiness, managed process ownership and diagnostics |
| Platform adapters | Paths, hardware detection, process control and secure credentials |

Keep the five execution port types: string, image, audio, video, json. Canvas presentation objects such as image cards and groups are not additional execution port types. Raw ComfyUI graph data stays inside templates/adapters.

## Proposed Data Contracts

Use versioned Pydantic schemas and matching strict TypeScript contracts.

- Project: schema version, ID, name, canvas objects, asset references and history references.
- Asset: ID, media type, managed location or explicit external reference, content hash, dimensions and provenance.
- Model record: ID, file identity, locations, category, compatibility evidence and dependency status.
- Engine connection: ID, kind, version, endpoint, ownership, runtime reference and readiness.
- Template: ID/version, required engine capabilities, model/custom-node dependencies, parameters and input/output mappings.
- Task: ID, run ID, action, immutable inputs, resolved parameters, execution location, template/model versions, status and output references.
- Credential: opaque reference to protected storage; never an inline workflow parameter.
- Event: run/task ID, sequence, timestamp, typed state/progress/output/error payload.

Validate endpoints and inputs at service boundaries. Persist schemas with explicit migration behavior; never silently reinterpret old projects.

## Execution and Reliability

1. Resolve an action and snapshot parameters, assets, template, model identity and execution location.
2. Validate required capabilities, engine readiness and dependencies.
3. Resolve upstream outputs, compute semantic cache identity, and check asset availability.
4. Queue or reuse results; dispatch asynchronously through the selected adapter.
5. Track actual engine/provider completion; retrieve and persist real outputs.
6. Atomically commit task outcome, asset records and cache entry; notify the UI.

Do not fabricate output filenames. Do not mark a submitted job as completed. Failed prerequisites block dependent work; independent work may continue under a documented policy.

Events must be correlated so late updates cannot overwrite a different run. Define reconnect/restart reconciliation for nonterminal tasks. An interrupted job with uncertain provider status must not be automatically resubmitted at potential duplicate cost.

ComfyUI adapters must resolve real output metadata after completion. WebUI and provider adapters normalize actual responses. Read current official APIs before implementing version-specific behavior.

## Cache Contract

Preserve NodeHash = Hash(NodeType + Params + UpstreamOutputHashes).

Canonical Params must include semantic execution settings: resolved seed, model identity/version, template/runner semantic version, provider identity where behavior differs, and input binding information. Upstream output hashes must identify actual content and port associations, not merely parent computation keys. Encode bindings in deterministic structured order, not a sorted multiset that loses meaning.

Direct assets and masks use content identity. URLs alone are not stable content hashes. Exclude canvas position, display labels and raw credentials. Namespace caches appropriately by project/credential reference where isolation requires it.

A cache hit requires accessible valid output assets. Publish cache entries only after successful durable output storage. A user-requested variant explicitly changes seed or supplies a persisted cache-bust nonce. Retries must distinguish retrieval of an existing remote job from new paid submission.

Test DAG cycles, binding changes, actual upstream output changes, mask/model changes, deterministic serialization and failure behavior whenever changing the core.

## Storage and Credentials

Use a small local database (SQLite is the implementation default) plus managed asset files. Keep project documents versioned, writes atomic, and filesystem/database reconciliation recoverable. Download generated remote media while it is available; external user imports may remain referenced with missing-file recovery.

Use OS-protected credentials behind a platform abstraction; do not create a plaintext fallback silently. Secrets remain backend-side and must be redacted from diagnostics. Bind the local backend to loopback by default and restrict CORS/origins; use session authorization for sensitive local operations.

Async service handlers must not block on scans, hashing, subprocess waits or database/disk operations. Use suitable asynchronous interfaces or offload bounded blocking work.

## Runtime Isolation and Portability

Separate managed ComfyUI and WebUI environments. No global pip installs or fallback to host Python. Support existing installations without taking ownership automatically.

An installation manifest records engine version, environment, paths and completion state. Stage downloads/setup, report progress, and recover safely from interruption. Verify managed process identity before termination; never treat an arbitrary PID as sufficient ownership proof.

The launcher may own Berry's backend process, but engine supervisors own managed ComfyUI/WebUI processes. External engines remain user-owned. Berry app updates and managed-engine updates are distinct operations; preserve models, projects, credentials and configuration. Track update state, compatibility and recovery before reporting success. See [Launcher and Environment Manager](LAUNCHER_MANAGER_REQUIREMENTS.md) for approved behavior.

Platform adapters contain Windows-specific process flags and paths. Model directories may be shared only when engine configuration and compatibility permit. Preserve legacy engine locations and environment variables unless an explicit migration is implemented.

Future non-NVIDIA discrete GPU support attaches through capability/runtime adapters. Do not add unrequested inference backends now.

## Validation and Outstanding Decisions

See [Roadmap](ROADMAP.md) for gates. Record exact versions, providers, reference models, workflow formats, packaging and credential choices in English architecture decision records during implementation. Do not assert hardware/provider support before verification.
