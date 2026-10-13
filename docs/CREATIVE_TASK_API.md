# Durable creation tasks and Agent history

New clients submit with `POST /api/v1/creative/submit`. A successful admission returns HTTP 202 with `task_id` and `status: queued` before inference finishes. The queue admits at most 64 outstanding tasks, with two execution slots and serialization per local connection. Exhausted admission returns HTTP 503 and `Retry-After: 5`; no provider job is submitted for a refused request.

Retrieve durable status and outputs with `GET /api/v1/creative/tasks/{task_id}`. Subscribe with `GET /api/v1/creative/tasks/{task_id}/events`. Each SSE message includes a task snapshot and monotonic sequence ID. `after_sequence` replays later durable transitions. Disconnecting never submits another inference request. The bundled client falls back to status retrieval for the same task on stream failure. The synchronous `/creative/execute` endpoint remains available for legacy clients.

Cancellation remains a request until confirmed. Queued cancellation prevents dispatch; active uninterruptible work may complete successfully and incur charges. Restart reconciliation records interrupted or uncertain work without automatically resubmitting it. Transition events, effective parameters, provider job IDs and output references are stored in SQLite. Inline credential fields are redacted.

Agent chat accepts `project_id` and `conversation_id`. The bundled panel resends the returned identity for follow-ups. `GET /api/v1/agent/conversation?project_id=...` retrieves the latest durable transcript for that project. Conversation identities cannot be reused in a different project. Retention is capped at 200 conversations globally and 100 messages per conversation; project deletion removes its conversations. Approved proposals use the shared task scheduler, preserve the originating project, and stop the chain after a failed step.

SQLite migrations add conversation and transition tables without discarding existing projects, tasks, assets or caches. Database initialization is serialized so concurrent first requests cannot observe an incomplete schema.

Mock and fixture tests establish these transport and persistence contracts. They do not establish real GPU/provider acceptance or clean-machine packaging.
