# Berry AI Studio Launcher Hub — API Specification & Integration Guide

Date: 2026-10-03. Status: approved specification; implementation in progress.
Parent PRD: [Launcher Hub PRD](LAUNCHER_HUB_PRD.md).
Milestones: [Implementation Milestones](LAUNCHER_HUB_MILESTONES.md).

---

## 1. Overview & Architecture Boundary

The Launcher Hub serves as the primary dashboard and environment control center for Berry AI Studio. Following the architectural invariant defined in `AGENTS.md` and `docs/LAUNCHER_MANAGER_REQUIREMENTS.md` (L11):
- **Authoritative Backend**: The FastAPI backend owns all process supervision, hardware detection, engine lifecycle, directory validation, and installation logic.
- **Featherweight Frontend**: The React / Tauri frontend acts as the presentation and orchestration layer, consuming backend REST endpoints and maintaining live client state via Zustand stores.

All endpoints are versioned under `/api/v1/`.

---

## 2. API Endpoints Specification

### 2.1 Hardware & GPU Monitoring

#### `GET /api/v1/hardware/gpu-stats`
Retrieves real-time GPU telemetry, utilization, VRAM metrics, and per-process memory consumption.

- **Request**: No parameters.
- **Response** (`200 OK`):
```json
{
  "has_gpu": true,
  "vendor": "nvidia",
  "name": "NVIDIA GeForce RTX 4090",
  "driver_version": "555.42.02",
  "temperature_c": 52,
  "utilization_pct": 38,
  "vram_total_mb": 24576,
  "vram_used_mb": 6348,
  "vram_free_mb": 18228,
  "processes": [
    {
      "pid": 14220,
      "process_name": "Berry Backend",
      "vram_used_mb": 128
    },
    {
      "pid": 19488,
      "process_name": "ComfyUI",
      "vram_used_mb": 5930
    }
  ]
}
```
- **Response (No GPU / Cloud-Only)** (`200 OK`):
```json
{
  "has_gpu": false,
  "vendor": "none",
  "name": "No Dedicated GPU",
  "driver_version": "",
  "temperature_c": null,
  "utilization_pct": null,
  "vram_total_mb": 0,
  "vram_used_mb": 0,
  "vram_free_mb": 0,
  "processes": []
}
```

---

### 2.2 Engine Instances & Lifecycle Management

#### `GET /api/v1/engines/instances`
Returns a unified catalog of all registered engine instances (both managed installations and external connected paths).

- **Request**: No parameters.
- **Response** (`200 OK`):
```json
{
  "instances": [
    {
      "id": "builtin-canvas",
      "type": "canvas",
      "name": "Infinite Canvas",
      "version": "v0.1.0",
      "is_managed": true,
      "is_builtin": true,
      "install_path": null,
      "status": "ready",
      "endpoint": null,
      "pid": null,
      "vram_used_mb": null
    },
    {
      "id": "comfyui-managed",
      "type": "comfyui",
      "name": "ComfyUI",
      "version": "v0.3.8",
      "is_managed": true,
      "is_builtin": false,
      "install_path": "C:\\Users\\User\\.ai-studio\\engines\\comfyui",
      "status": "running",
      "endpoint": "http://127.0.0.1:8188",
      "pid": 19488,
      "vram_used_mb": 5930
    },
    {
      "id": "webui-external",
      "type": "webui",
      "name": "SD WebUI (External)",
      "version": "v1.9.3",
      "is_managed": false,
      "is_builtin": false,
      "install_path": "D:\\stable-diffusion-webui",
      "status": "stopped",
      "endpoint": "http://127.0.0.1:7860",
      "pid": null,
      "vram_used_mb": null
    },
    {
      "id": "builtin-agents",
      "type": "agents",
      "name": "AI Agents",
      "version": "v0.1.0",
      "is_managed": true,
      "is_builtin": true,
      "install_path": null,
      "status": "ready",
      "endpoint": null,
      "pid": null,
      "vram_used_mb": null
    }
  ]
}
```

Instance `status` values: `ready` (for built-in views), `running`, `stopped`, `starting`, `updating`, `error`, `not_installed`.

---

### 2.3 Auto-Detection & Path Binding

#### `GET /api/v1/engines/detect`
Initiates an on-demand scan of standard installation paths across user drives to discover pre-existing ComfyUI and SD WebUI directories.

- **Request**: Query parameters (optional): `force_rescan` (boolean, default: `false`).
- **Response** (`200 OK`):
```json
{
  "detected": [
    {
      "engine_type": "comfyui",
      "path": "D:\\ComfyUI_windows_portable\\ComfyUI",
      "version": "v0.3.8 (git 9a4f21b)",
      "has_python_env": true,
      "python_executable": "D:\\ComfyUI_windows_portable\\python_embeded\\python.exe",
      "recommended_name": "ComfyUI Portable"
    }
  ]
}
```

#### `POST /api/v1/engines/bind`
Binds an existing local directory as an external engine instance.

- **Request Payload**:
```json
{
  "engine_type": "comfyui",
  "name": "My ComfyUI",
  "path": "D:\\ComfyUI_windows_portable\\ComfyUI",
  "port": 8188,
  "extra_args": ["--lowvram", "--fast"]
}
```
- **Validation**:
  - Checks existence of target directory.
  - Verifies presence of engine signature file (`main.py` for ComfyUI, `webui-user.bat` or `launch.py` for WebUI).
  - Returns `400 Bad Request` with structured diagnostic if signature is missing.
- **Response** (`201 Created`):
```json
{
  "id": "comfyui-ext-d-comfyui",
  "engine_type": "comfyui",
  "name": "My ComfyUI",
  "path": "D:\\ComfyUI_windows_portable\\ComfyUI",
  "status": "stopped"
}
```

#### `DELETE /api/v1/engines/unbind/{instance_id}`
Removes an external engine binding. This operation is **strictly non-destructive**: zero files are deleted from the disk.

- **Response** (`200 OK`):
```json
{
  "success": true,
  "message": "Engine unpinned successfully"
}
```

---

### 2.4 Mirror Acceleration & Deployment Configuration

#### `GET /api/v1/installer/mirrors`
Returns the available mirror presets and the currently selected configuration.

- **Response** (`200 OK`):
```json
{
  "active_preset": "china_mainland",
  "presets": [
    {
      "id": "direct",
      "name": "Direct (Official Global)",
      "git_mirror": null,
      "pypi_mirror": "https://pypi.org/simple",
      "hf_mirror": "https://huggingface.co"
    },
    {
      "id": "china_mainland",
      "name": "China Mainland (Accelerated)",
      "git_mirror": "https://mirror.ghproxy.com/",
      "pypi_mirror": "https://pypi.tuna.tsinghua.edu.cn/simple",
      "hf_mirror": "https://hf-mirror.com"
    },
    {
      "id": "custom",
      "name": "Custom",
      "git_mirror": null,
      "pypi_mirror": null,
      "hf_mirror": null
    }
  ]
}
```

#### `PUT /api/v1/installer/mirrors`
Updates the active mirror preset or custom URLs.

- **Request Payload**:
```json
{
  "active_preset": "china_mainland",
  "custom_git_mirror": null,
  "custom_pypi_mirror": null,
  "custom_hf_mirror": null
}
```
- **Response** (`200 OK`): Returns updated mirror configuration.

---

### 2.5 Real-Time Engine Logs & Diagnostics

#### `GET /api/v1/runtime/{instance_id}/logs`
Fetches recent log lines for a running or terminated engine instance.

- **Request**: Query parameter `lines` (integer, default: 200, max: 2000).
- **Response** (`200 OK`):
```json
{
  "instance_id": "comfyui-managed",
  "total_lines": 142,
  "logs": [
    "[2026-10-03 18:30:01] Starting ComfyUI on port 8188...",
    "[2026-10-03 18:30:02] Loading custom nodes...",
    "[2026-10-03 18:30:04] Total VRAM 24576 MB, device: cuda:0"
  ]
}
```

---

## 3. Frontend Zustand Store Architecture

### 3.1 `useNavigationStore`
- `activeView`: `'launcher' | 'canvas' | 'comfyui' | 'webui' | 'agents' | 'settings'`
- `isRailCollapsed`: boolean
- `setActiveView(view: ViewType)`
- `toggleRail()`

### 3.2 `useEngineStore`
- `instances`: `EngineInstance[]`
- `isLoading`: boolean
- `isDeploying`: boolean
- `deploymentProgress`: `{ step: string; percent: number; logs: string[] }`
- `fetchInstances()`
- `startEngine(id: string)`
- `stopEngine(id: string)`
- `unbindEngine(id: string)`
- `bindEngine(payload: BindEnginePayload)`

### 3.3 `useHardwareStore`
- `gpuStats`: `GpuStats | null`
- `isPopoverOpen`: boolean
- `pollStats()`
- `setPopoverOpen(open: boolean)`

### 3.4 `useSettingsStore`
- `exitPolicy`: `'prompt' | 'close_all' | 'keep_running'`
- `rememberExitChoice`: boolean
- `mirrorPreset`: `'direct' | 'china_mainland' | 'custom'`
- `setExitPolicy(policy, remember)`
- `setMirrorPreset(preset)`
