# Security Architecture and Guidelines

Date: 2026-10-07
Status: Active security documentation for Berry AI Studio
Related: Issue #144, ARCHITECTURE.md, AGENTS.md

## Overview

Berry AI Studio implements a layered security model that balances native desktop capabilities with web content security. The application consists of a Rust/Tauri native shell that hosts a React/TypeScript frontend communicating with a FastAPI Python backend.

## Security Principles

1. **Least Privilege**: Native capabilities are granted only to trusted local origins
2. **Defense in Depth**: Multiple security layers (CSP, capability scoping, origin validation)
3. **Isolation**: Local engines run in sandboxed environments with no global host pollution
4. **Content Security**: External content (generated images, API responses) is isolated from native privileges

## Architecture Components

```
┌─────────────────────────────────────────────────────────┐
│  Tauri Native Shell (Rust)                              │
│  - Window management (minimize, maximize, close)        │
│  - Backend process supervision                          │
│  - Capability enforcement                               │
└─────────────────────────────────────────────────────────┘
                         │
                         ↓ IPC (scoped to localhost)
┌─────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                │
│  Origin: http://127.0.0.1:8000                          │
│  - Canvas UI, creation controls                         │
│  - CSP-enforced content policy                          │
└─────────────────────────────────────────────────────────┘
                         │
                         ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────┐
│  Backend (FastAPI + Python)                             │
│  Bound to: 127.0.0.1:8000                               │
│  - Workflow execution, model management                 │
│  - ComfyUI/WebUI engine coordination                    │
└─────────────────────────────────────────────────────────┘
```

## Native Capabilities

### Capability Scoping

The Tauri capability system grants native window control permissions exclusively to local origins:

**File**: `frontend/src-tauri/capabilities/default.json`

```json
{
  "identifier": "default",
  "description": "Grants window control permissions to the local backend origin",
  "windows": ["main"],
  "permissions": [
    "core:window:allow-minimize",
    "core:window:allow-maximize",
    "core:window:allow-unmaximize",
    "core:window:allow-toggle-maximize",
    "core:window:allow-close",
    "core:window:allow-start-dragging",
    "core:window:allow-is-maximized",
    "core:window:allow-set-focus"
  ],
  "remote": {
    "urls": [
      "http://127.0.0.1:*",
      "http://localhost:*"
    ]
  }
}
```

**Security Properties**:
- Only content served from `127.0.0.1` or `localhost` receives native window control permissions
- External content loaded via `<iframe>`, images, or API responses cannot invoke native commands
- Commands are validated at the Rust boundary before execution

### Supported Native Commands

| Command | Purpose | Risk Level | Validation |
|---------|---------|------------|------------|
| `close_app` | Graceful shutdown with backend lifecycle management | Medium | Checks for active tasks, respects refusal |
| `minimize_app` | Minimize window | Low | Direct window API call |
| `maximize_app` | Toggle maximize state | Low | Window state management |

## Content Security Policy (CSP)

The CSP restricts what content can be loaded and executed, preventing injection attacks and unauthorized resource access.

**File**: `frontend/src-tauri/tauri.conf.json`

```
default-src 'self' tauri: http://127.0.0.1:* http://localhost:*;
img-src 'self' tauri: asset: data: blob: http://127.0.0.1:* http://localhost:* https:;
media-src 'self' data: blob: http://127.0.0.1:* http://localhost:* https:;
connect-src 'self' tauri: http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:* https:;
style-src 'self' 'unsafe-inline';
script-src 'self' 'wasm-unsafe-eval';
worker-src 'self' blob:;
frame-src 'none';
object-src 'none';
base-uri 'self'
```

### CSP Directive Breakdown

| Directive | Policy | Rationale |
|-----------|--------|-----------|
| `default-src` | `'self' tauri: http://127.0.0.1:* http://localhost:*` | Only local origins and Tauri protocol can load resources by default |
| `img-src` | Includes `https:` | Allow external images from AI generation APIs (Fal.ai, SiliconFlow, etc.) |
| `media-src` | Includes `https:` | Allow video/audio from external APIs for future video generation features |
| `connect-src` | Local + `https:` + WebSocket | Backend API, ComfyUI WebSocket, cloud provider APIs |
| `script-src` | `'self' 'wasm-unsafe-eval'` | Only bundled scripts; wasm-eval for React/Vite hot reload in dev mode |
| `style-src` | `'self' 'unsafe-inline'` | Tailwind CSS requires inline styles at runtime |
| `frame-src` | `'none'` | **Block all iframes** to prevent clickjacking and content injection |
| `object-src` | `'none'` | **Block Flash and legacy plugins** |
| `base-uri` | `'self'` | Prevent `<base>` tag injection attacks |
| `worker-src` | `'self' blob:` | Allow Web Workers for async processing |

### Why `'unsafe-inline'` for Styles?

Tailwind CSS generates utility classes dynamically and applies styles via the `style` attribute. Alternatives:
- **Nonce-based CSP**: Would break Vite's hot module reload in development
- **CSS-in-JS with hashed styles**: Requires significant architecture changes
- **Risk mitigation**: Script execution is still blocked; inline styles alone cannot execute code

The risk is accepted because:
1. `script-src` does not include `'unsafe-inline'`, so `<style>` tags cannot contain `javascript:` URIs
2. Style injection alone cannot compromise the native capability boundary
3. The primary attack vectors (XSS, code injection) remain blocked

### Why `'wasm-unsafe-eval'` for Scripts?

Required for:
- Vite's hot module replacement (HMR) in development mode
- React Fast Refresh dynamic module loading
- Future WebAssembly-based image processing (e.g., client-side upscaling)

**Production Alternative**: The build process can generate a stricter CSP for release builds that removes `'wasm-unsafe-eval'` if WASM features are not used.

## Origin Validation

### Backend Binding

The FastAPI backend binds exclusively to `127.0.0.1` (localhost), not `0.0.0.0`:

```python
uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
```

**Security Properties**:
- Backend is not exposed to the local network
- Only processes on the same machine can connect
- Prevents lateral movement in compromised network environments

### Window URL Configuration

The Tauri window is explicitly configured to navigate to the backend origin:

```json
{
  "app": {
    "windows": [{
      "url": "http://127.0.0.1:8000",
      ...
    }]
  }
}
```

This ensures:
- The main window always loads from a trusted origin
- Capabilities are applied correctly on first navigation
- No accidental navigation to external sites with native privileges

## Threat Model

### In-Scope Threats

| Threat | Mitigation |
|--------|-----------|
| **Malicious generated images with embedded scripts** | CSP blocks script execution; images are rendered as data, not executed |
| **Compromised cloud API returning malicious content** | CSP isolates external content; no native capabilities granted to API responses |
| **User imports malicious HTML file to canvas** | Sanitized during import; CSP blocks inline scripts in imported content |
| **XSS via workflow parameter injection** | React's JSX escaping; CSP script-src restrictions |
| **Clickjacking via iframe injection** | CSP `frame-src 'none'` blocks all iframes |
| **CSRF from local network** | Backend bound to 127.0.0.1 only; CORS configured for localhost origins |
| **Unauthorized native command invocation** | Capability scoping limits commands to local origins; Rust validates all invocations |

### Out-of-Scope

- **Physical access attacks**: User with physical access can modify application files
- **Compromised host OS**: Malware with admin/root privileges can bypass all application-level security
- **Supply chain attacks**: Dependency compromise requires separate mitigation (SCA, SBOM, vendoring)
- **Social engineering**: User intentionally running malicious workflows or importing dangerous files

## Secure Coding Practices

### Frontend (TypeScript)

1. **Never use `dangerouslySetInnerHTML`** for user-provided content
2. **Validate API responses** before rendering
3. **Sanitize file imports** and check MIME types
4. **Use type-safe Tauri API wrappers** (`@tauri-apps/api`) instead of raw `__TAURI__` access

### Backend (Python)

1. **Bind to `127.0.0.1`** only, never `0.0.0.0`
2. **Validate all workflow parameters** with Pydantic schemas
3. **Sanitize file paths** to prevent directory traversal
4. **Use subprocess isolation** for engine execution (dedicated user accounts in production)
5. **Never execute user-provided Python/JavaScript** in the backend process

### Rust/Tauri

1. **Validate command payloads** before calling window APIs
2. **Check process ownership** before sending shutdown signals
3. **Use `Child` handles** properly; clean up zombie processes
4. **Log security-relevant events** (command invocations, capability grants)

## Testing Security

### Automated Tests

```bash
# Frontend type checking
cd frontend && npm run typecheck

# Rust capability and window control tests
cd frontend/src-tauri && cargo test

# Backend API security tests
cd backend && python -m pytest tests/
```

### Manual Security Testing

1. **Capability Isolation**:
   - Open DevTools in the Tauri window
   - Try to invoke `window.__TAURI__.core.invoke('close_app')` from external origin
   - Expected: Command should fail with capability error

2. **CSP Validation**:
   - Inject a `<script>alert('XSS')</script>` into a workflow parameter
   - Expected: Script should not execute; CSP violation logged in console

3. **Origin Validation**:
   - Attempt to connect to backend from external network
   - Expected: Connection refused (backend bound to 127.0.0.1)

4. **Content Isolation**:
   - Import an image from an external API
   - Verify it renders but cannot access native APIs
   - Expected: Image displays; no access to `close_app` or other native commands

## Production Hardening (Future)

The following hardening measures are recommended for production deployments:

1. **Code Signing**: Sign Windows executables with EV certificate to avoid SmartScreen warnings
2. **Update Verification**: Implement signature verification for auto-updates
3. **Secrets Management**: Use OS credential store (Windows Credential Manager, macOS Keychain) for API keys
4. **Telemetry**: Log capability invocations and CSP violations for monitoring
5. **Sandboxing**: Run local engines in restricted user accounts or containers
6. **Network Policies**: Add firewall rules to block unexpected outbound connections

## Incident Response

If a security issue is discovered:

1. **Do not** disclose publicly until a fix is available
2. Contact the maintainers via private channels (security@berryai.studio or GitHub Security Advisory)
3. Provide reproduction steps, affected versions, and impact assessment
4. Work with maintainers on coordinated disclosure timeline

## References

- [Tauri Security Documentation](https://v2.tauri.app/security/)
- [CSP Level 3 Specification](https://www.w3.org/TR/CSP3/)
- [OWASP Desktop App Security](https://owasp.org/www-community/vulnerabilities/)
- Berry AI Studio ARCHITECTURE.md, AGENTS.md
- Issue #144: Validation of native capabilities and CSP

---

**Last Updated**: 2026-10-07
**Next Review**: Before v0.1.0 release (see ROADMAP.md M5)
