# Engine Connection Routing (Issue #127)

## Overview

This document describes how Berry AI Studio resolves and routes execution and lifecycle operations through the selected engine connection, ensuring that all operations (uploads, prompt submission, progress retrieval, output downloads, and cancellation) use the same resolved connection.

## Canonical Connection Flow

```
Frontend Selection → Backend Request → Connection Registry → Resolved Client → Engine Endpoint
```

### Connection Identity

Each engine connection has a stable identifier (`connection_id`) that:
- Uniquely identifies the connection in the registry
- Persists across UI selections
- Determines endpoint resolution (protocol, host, port, URL path)
- Identifies ownership (managed vs external)
- Defines capabilities (ComfyUI vs WebUI API contract)

### Connection Types

**Managed Connections** (`ownership: "managed"`):
- Berry controls the engine lifecycle (start/stop)
- Default IDs: `"comfyui-managed"`, `"webui-managed"`
- Endpoint configured at installation time
- Can use non-localhost addresses for containerized deployments

**External Connections** (`ownership: "external"`):
- User-controlled engines (no process management)
- Custom IDs: user-defined (e.g., `"studio-comfy-a100"`)
- Full URL specified by user (protocol + host + port + path)
- Berry never attempts to start/stop these engines

## Request Flow

### 1. Frontend: Selection to Request

```typescript
// User selects connection in UI
const selectedConnection = engineStore.connections.find(c => c.id === selectedId);

// Pass connection_id in API request
const result = await api.post('/api/v1/creative/execute', {
  action: 'txt2img',
  prompt: 'a red apple',
  connection_id: selectedConnection.id,  // Stable identifier
  // ... other parameters
});
```

### 2. Backend: Request to Resolution

```python
# creative_runner.py
async def execute(self, req: CreativeActionRequest) -> CreativeActionResult:
    # Resolve connection from request
    connection = self._resolve_connection(req.connection_id, req.engine_id)
    
    # Create client for this specific connection
    client = self._create_client(connection)
    
    # Execute using resolved client
    result = await self._run_comfy(req, client, input_file, mask_file)
```

### 3. Connection Resolution Logic

```python
def _resolve_connection(
    self, 
    connection_id: Optional[str], 
    engine_id: Optional[str]
) -> EngineConnection:
    """
    Resolve connection with fallback chain:
    1. Explicit connection_id from request
    2. engine_id mapped to default managed connection
    3. Raise error if neither resolves
    """
    if connection_id:
        conn = engine_manager.get_connection(connection_id)
        if not conn:
            raise ValueError(f"Connection '{connection_id}' not found")
        return conn
    
    if engine_id:
        # Legacy fallback for engine_id
        if engine_id == "comfyui":
            return engine_manager.get_connection("comfyui-managed")
        elif engine_id == "webui":
            return engine_manager.get_connection("webui-managed")
    
    raise ValueError("No connection_id or engine_id provided")
```

### 4. Client Creation

```python
def _create_client(self, connection: EngineConnection):
    """Create type-specific client for resolved connection."""
    if connection.engine_type == EngineType.COMFYUI:
        # Parse connection URL for host/port
        parsed = urlparse(connection.url)
        return ComfyUIClient(
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or 8188,
            base_url=connection.url  # Use full configured URL
        )
    elif connection.engine_type == EngineType.WEBUI:
        return WebUIRunner(endpoint_url=connection.url)
    else:
        raise ValueError(f"Unsupported engine type: {connection.engine_type}")
```

## Cache Isolation

Connections must be isolated in the cache to prevent cross-connection result reuse:

```python
def compute_creative_cache_hash(
    req: CreativeActionRequest,
    connection_id: str,  # Now required
    input_hash: str = "",
    mask_hash: str = "",
) -> str:
    canonical_payload = {
        # ... existing fields
        "connection_id": connection_id,  # Isolate by connection
        "runner_version": "0.3.0",  # Bumped for connection routing
    }
    return hashlib.sha256(json.dumps(canonical_payload, sort_keys=True).encode()).hexdigest()
```

## Lifecycle Operations

### Start/Stop Operations

```python
# Only allowed for MANAGED connections
if connection.ownership != EngineOwnership.MANAGED:
    raise ValueError(f"Cannot start/stop external connection '{connection.id}'")

# Use supervisor associated with managed connection
if connection.id == "comfyui-managed":
    await comfy_supervisor.start()
```

### Cancellation

```python
async def cancel_task(self, task_id: str) -> Dict[str, Any]:
    # Retrieve connection_id from active task metadata
    task_info = self.active_tasks.get(task_id)
    if not task_info:
        return {"success": False, "message": "Task not found"}
    
    connection_id = task_info.get("connection_id")
    connection = engine_manager.get_connection(connection_id)
    
    # Create client for cancellation
    client = self._create_client(connection)
    
    # Send interrupt to correct endpoint
    if connection.engine_type == EngineType.COMFYUI:
        await client.interrupt()
```

## Frontend Integration

### Connection URL Usage

```typescript
// BEFORE (Issue #127 - reconstructs URL from port)
const url = `http://localhost:${connection.port}`;

// AFTER (Use configured URL)
const url = connection.url;  // e.g., "http://127.0.0.1:8188" or "https://studio.example.com:8443/comfy"
```

### Lifecycle Dispatch

```typescript
// BEFORE (checks engine type string)
if (engine.type === 'comfyui') {
  await startComfyUI();
}

// AFTER (checks connection ownership)
const connection = engineStore.getConnection(selectedConnectionId);
if (connection.ownership === 'managed') {
  await api.post(`/api/v1/engines/${connection.id}/start`);
}
```

## Error Handling

### Unknown Connection

```python
# Request specifies connection_id that doesn't exist
raise ValueError(
    f"Engine connection '{connection_id}' not found. "
    f"Available connections: {list(engine_manager.list_connections().keys())}"
)
```

### Unavailable Connection

```python
# Connection exists but endpoint is offline
status = await client.get_status()
if not status.get("online"):
    raise RuntimeError(
        f"Engine connection '{connection.id}' is offline. "
        f"Please start the engine or check the connection URL."
    )
```

### Incompatible Connection

```python
# Request requires ComfyUI but connection is WebUI
if req.action == CreativeActionType.TXT2VIDEO and connection.engine_type != EngineType.COMFYUI:
    raise ValueError(
        f"Action '{req.action}' requires ComfyUI but connection "
        f"'{connection.id}' is {connection.engine_type}"
    )
```

## Migration Path

### Phase 1: Backward Compatibility (This PR)

- Accept both `connection_id` (new) and `engine_id` (legacy)
- Map `engine_id` to default managed connections
- Deprecation warning logged when `engine_id` used without `connection_id`

### Phase 2: Frontend Adoption (Next PR)

- Update all frontend API calls to pass `connection_id`
- Remove URL reconstruction from port
- Use connection registry for lifecycle dispatch

### Phase 3: Deprecation (Future PR)

- Remove `engine_id` fallback logic
- Require explicit `connection_id` in all requests
- Update API documentation

## Testing Strategy

### Unit Tests

- Connection resolution with valid/invalid IDs
- Client creation for ComfyUI and WebUI connections
- Cache hash includes connection_id
- Error messages for unknown/unavailable connections

### Integration Tests

- Two distinguishable connections (different ports)
- Verify correct endpoint receives each operation
- Upload → queue → poll → download uses same connection
- Cancellation targets correct connection
- Selection change doesn't redirect running task

### Contract Tests (Mocked)

- Parse non-localhost URLs correctly
- Handle custom ports and URL paths
- Managed vs external ownership enforcement

## Related Issues

- **Resolves**: #127 (Engine connection routing)
- **Depends on**: #158 (Asset uploads), #159 (Mask normalization)
- **Related**: #125 (Connection save persistence - future work)
