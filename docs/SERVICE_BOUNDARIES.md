# Execution and UI contract boundaries

`main.py` composes transport adapters with injected services. Its service factories
read application-owned dependencies at request time, so fixture replacements and
optional runtime composition remain possible without changing public endpoints.

- `WorkflowExecutionService` owns planning and durable DAG execution. Both consume
  the canonical resolved workflow specification; typed runner events retain the
  five execution-port types and the deterministic content cache contract.
- `CreationServices` composes the durable task store, bounded admission scheduler
  and creative runner. Submission, status and SSE are separate transports.
- `TaskControlService` owns one cancellation decision tree shared by task and
  legacy workflow routes. Cancellation requests are durable; they do not assert
  that unsupported remote work or charges stopped.
- `AssetService` owns verified uploads, normalized base64 decoding and safe
  content descriptors. Routes map missing assets to 404 and produce FileResponse.
  The existing media validator still raises transport-compatible validation
  errors; replacing those errors is a separate compatibility change.
- `EngineService` owns bounded connection discovery/configuration and serialized
  managed start/stop/status. EngineManager retains authoritative connection
  identity, readiness and external ownership; the shared Rust runtime owns only
  Berry backend process supervision.

Heterogeneous JSON port payloads and validated runtime diagnostic dictionaries
intentionally use Python `Any`; the public models and runner/service signatures
remain typed. This exception does not permit exposing low-level tensors. Frontend
production code rejects explicit `any`; test fixture casts remain outside this
targeted rule because incomplete fixture objects are not production contracts.
Download clients share the backend `{tasks: [...]}` envelope and fail invalid
responses instead of waiting indefinitely for another shape.

Presentation uses Tailwind classes. Shared progress indicators use SVG geometry
attributes and expose an accessible observed or indeterminate value. Four canvas
components retain dynamic inline geometry as an explicit compatibility exception:
CanvasAgentPrompt and QuickAddMenu position transient menus at pointer coordinates;
WorkspaceFrameNode renders persisted variable frame bounds; InpaintModal positions
and sizes the brush cursor from pointer/brush measurements. Those values cannot
be enumerated as Tailwind classes. The exception covers geometry only, not colors,
typography or arbitrary visual styles. Other components reject JSX style attributes.
