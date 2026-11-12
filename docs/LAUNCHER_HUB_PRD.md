# Berry AI Studio Launcher Hub — Product Requirements Document

Date: 2026-10-03. Status: requirements confirmed; implementation pending.
Governing Documents: [Product Vision](PRODUCT_VISION.md), [PRD](PRD.md), [Architecture](ARCHITECTURE.md), [Launcher Requirements L01–L12](LAUNCHER_MANAGER_REQUIREMENTS.md).

---

## 1. Problem Statement

The current application opens directly into the infinite canvas workspace. Users have no centralized entry point to:
- Choose which workspace to enter (Canvas, ComfyUI, WebUI, Agents).
- View and manage the lifecycle of local engine installations.
- Deploy, update, or configure engines before starting creative work.
- Monitor GPU/VRAM utilization across running engine processes.

The existing `EnvironmentManagerModal` provides engine management as a secondary modal overlay, which lacks the prominence, discoverability, and navigational structure required for a hub-style experience.

## 2. Solution Overview

Introduce a **Launcher Hub** as the application's default landing view, paired with a **Global Navigation Rail** that provides persistent, one-click switching between all major workspaces. The Launcher Hub replaces the current "open directly into canvas" behavior with a centralized dashboard inspired by Comfy Desktop's instance manager pattern.

### Reference Design

The Comfy Desktop launcher (see attached reference screenshot) demonstrates the instance-card pattern: a searchable grid of engine instances, each showing name, version, status, and contextual actions. Berry's Launcher Hub extends this concept with:
- Multiple workspace types (not just ComfyUI instances).
- Integrated GPU/VRAM monitoring in the top bar.
- Deployment progress visualization with real-time log streaming.
- Local engine auto-detection and manual path binding.

---

## 3. Confirmed Requirements

### 3.1 Default Startup Behavior

| ID | Requirement | Acceptance Condition |
| --- | --- | --- |
| LH-01 | **Default to Launcher Hub** | Every application launch opens the Launcher Hub view first. The user must explicitly navigate to another workspace. |
| LH-02 | **No "Set Default" shortcut (v1)** | The first release does not support "skip launcher and open canvas directly" as a user preference. This may be added later as a settings option. |
| LH-03 | **Featherweight startup preserved** | The Launcher Hub renders immediately without waiting for backend readiness, GPU detection, or engine health checks. Status indicators populate asynchronously as data arrives. |

### 3.2 Global Navigation Rail (Left Sidebar)

| ID | Requirement | Acceptance Condition |
| --- | --- | --- |
| LH-10 | **Collapsible icon rail** | A narrow (56px) left-side vertical icon bar is always visible. It collapses to icon-only mode and can expand to show labels on hover or toggle. |
| LH-11 | **Navigation items** | Top section: 🏠 Home (Launcher Hub), 🎨 Infinite Canvas, 🧩 ComfyUI, 🖼️ WebUI, 🤖 Agents. Bottom section: ⚙️ Settings, 💻 System Status. |
| LH-12 | **Live status indicators on icons** | If an engine (ComfyUI/WebUI) is running in the background, its rail icon displays a green dot overlay. If a generation task is actively running, show a pulsing animation or spinner badge. |
| LH-13 | **View state preservation (Keep-Alive)** | Switching between views does NOT destroy component state. The canvas retains node positions, zoom level, and selection. Embedded engine views retain their session. Views are kept alive via CSS visibility toggling or equivalent non-destructive technique. |
| LH-14 | **Engine embedding** | ComfyUI and WebUI views are rendered as embedded webviews (iframe or Tauri webview) within the main content area. A small utility toolbar above the embedded view provides: "Open in Browser", "Refresh", "Open Directory". |

### 3.3 Launcher Hub View — Instance Cards

| ID | Requirement | Acceptance Condition |
| --- | --- | --- |
| LH-20 | **Card grid layout** | The Launcher Hub displays workspace/engine entries as a responsive card grid, similar to Comfy Desktop's instance grid. |
| LH-21 | **Card types** | Cards exist for: Infinite Canvas (always available, no deployment needed), ComfyUI (managed or external), SD WebUI (managed or external), Agents workspace. A special "+ New Instance / Add Engine" card allows adding new engine installations. |
| LH-22 | **Status indicator per card** | Each card displays a status badge: 🟢 Running, ⚫ Stopped, 🟡 Update Available, 🔴 Error/Failed, ⚪ Not Installed. |
| LH-23 | **Version display** | Cards for installed engines show the current version string (e.g., `v0.38.2`, `Stable`, or the git short hash). |
| LH-24 | **Primary action button** | Each card has a primary action: "Open" (for running engines), "Start" (for stopped engines), "Install" (for uninstalled engines). |
| LH-25 | **Three-dot context menu** | Each installed engine card has a `⋮` menu with: Configure (port, launch args like `--xformers`, `--lowvram`, `--cpu`), View Logs, Open Install Directory, Check for Updates, Uninstall / Unbind. |

### 3.4 Engine Process Lifecycle Management

| ID | Requirement | Acceptance Condition |
| --- | --- | --- |
| LH-30 | **Start/Stop control** | Users can start and stop managed engines from the Launcher Hub or from the navigation rail context menu. Starting an engine transitions its card status from Stopped → Starting → Running. |
| LH-31 | **Application exit dialog** | When the user closes the application window while one or more managed engines are still running, a confirmation dialog appears: *"ComfyUI and/or WebUI are still running. Close them too?"* with options: "Close All", "Keep Engines Running", and a checkbox "Remember my choice". |
| LH-32 | **External engine preservation** | External (user-owned, manually bound) engine processes are NEVER terminated by Berry, regardless of the exit policy. The exit dialog only mentions Berry-managed engines. |
| LH-33 | **Crash recovery indication** | If a managed engine process exits unexpectedly, the card transitions to 🔴 Error status with a "View Logs" and "Restart" action. |

### 3.5 Local Engine Detection & Deployment

| ID | Requirement | Acceptance Condition |
| --- | --- | --- |
| LH-40 | **Auto-detection scan** | On first launch (or on user request), Berry scans common Windows directories for existing ComfyUI and SD WebUI installations. Scan targets include: same-drive common paths, Desktop, known portable package directories (`ComfyUI_windows_portable`, `秋叶整合包 / A1111-stable-diffusion-webui`, `stable-diffusion-webui`). |
| LH-41 | **Detection heuristics** | ComfyUI is identified by the presence of `main.py` + `comfy/` directory. SD WebUI is identified by `webui-user.bat` or `launch.py` + `modules/` directory. Upon detection, Berry reads version info (git describe, or file-based version markers). |
| LH-42 | **Manual path binding** | The "+ New Instance" card and a prominent "Browse…" button allow users to manually select a directory. Berry validates the directory structure and presents the detected engine type and version for confirmation. |
| LH-43 | **Managed installation (one-click deploy)** | Users can choose "Install New ComfyUI" or "Install New WebUI" from the "+ New Instance" card. Berry downloads and installs the engine into its sandboxed directory (`~/.ai-studio/engines/comfyui/` or `~/.ai-studio/engines/webui/`), following the Zero Host Pollution invariant. |
| LH-44 | **Deployment progress UI** | During installation, a modal drawer/panel slides open showing: overall progress bar, current step description, real-time scrolling log output (stdout/stderr), and a Cancel button. |
| LH-45 | **Mirror acceleration** | The deployment settings include a network mirror selector with presets: Direct (GitHub/PyPI/HuggingFace), China Mainland (GitHub mirror proxy, Tsinghua/Aliyun pip mirror, HF-Mirror). Users can also specify custom mirror URLs. The selected mirror configuration is persisted in application settings. |

### 3.6 GPU & VRAM Monitoring

| ID | Requirement | Acceptance Condition |
| --- | --- | --- |
| LH-50 | **Top bar GPU summary** | The application's top navigation bar (right side) displays a compact GPU status string: e.g., `RTX 4090 · 6.2G / 24G (25%)`. If no NVIDIA GPU is detected, show `No GPU · Cloud Mode`. |
| LH-51 | **Hover detail popover** | Hovering over the GPU summary expands a floating card showing: GPU model name, driver version, GPU temperature, GPU utilization %, total/used/free VRAM, and a per-process VRAM breakdown (Berry Backend, ComfyUI, WebUI, Other). |
| LH-52 | **Polling interval** | GPU stats are polled every 3 seconds when the popover is closed, and every 1 second when the popover is open. Polling uses the backend `/api/v1/hardware/gpu-stats` endpoint, which calls `nvidia-smi` or equivalent. |
| LH-53 | **Non-NVIDIA graceful degradation** | On systems without NVIDIA GPUs (or without `nvidia-smi`), the GPU monitor displays "GPU monitoring unavailable" and does not poll. The application remains fully functional in cloud-only mode. |

---

## 4. Architecture & Technical Design

### 4.1 Frontend Architecture Change

The current `App.tsx` renders the canvas as the only main view. The Launcher Hub introduces a **view router** pattern:

```
App.tsx
├── GlobalNavRail (left sidebar, always visible)
├── ViewContainer (main content area, switches between views)
│   ├── LauncherHubView (default on startup)
│   ├── CanvasView (existing FlowCanvas + CreationDock)
│   ├── ComfyUIView (embedded webview/iframe)
│   ├── WebUIView (embedded webview/iframe)
│   ├── AgentsView (existing AgentPanel, promoted to full view)
│   └── SettingsView
├── GpuStatusBar (top-right, persistent)
└── Modals (InpaintModal, UpscaleModal, VideoModal, CloudSettingsModal, DeploymentDrawer)
```

**Key implementation decisions:**
- **View switching**: Use a Zustand `navigationStore` with an `activeView` enum. All views are rendered simultaneously but only the active view has `visibility: visible` / `display: block`. This preserves React component state across switches (Keep-Alive behavior).
- **No React Router**: Since this is a Tauri desktop app (not a multi-page web app), view switching is managed by Zustand store state, not URL-based routing.
- **Engine embedding**: ComfyUI and WebUI are embedded via `<iframe>` pointing to their local HTTP endpoints (e.g., `http://127.0.0.1:8188`). Tauri's `tauri.conf.json` must allowlist these origins for CSP. The iframe is wrapped in a container with a utility toolbar.

### 4.2 Backend API Extensions

The following new or extended endpoints support the Launcher Hub:

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `GET /api/v1/hardware/gpu-stats` | GET | Real-time GPU utilization, VRAM usage, temperature, per-process breakdown. |
| `GET /api/v1/engines/detect` | GET | Trigger auto-detection scan for existing local engine installations. Returns list of detected engine paths with type and version. |
| `POST /api/v1/engines/bind` | POST | Bind an externally detected or user-specified engine directory as an external engine instance. |
| `POST /api/v1/engines/unbind/{id}` | POST | Remove binding for an external engine (does not delete files). |
| `GET /api/v1/engines/instances` | GET | List all registered engine instances (managed + external) with current status. |
| `POST /api/v1/runtime/{engine_id}/configure` | POST | Update engine launch configuration (port, extra CLI args). |
| `GET /api/v1/runtime/{engine_id}/logs` | GET | Stream or retrieve recent log output for a managed engine process. |
| `GET /api/v1/installer/mirrors` | GET | List available mirror presets and current selection. |
| `PUT /api/v1/installer/mirrors` | PUT | Update the active mirror configuration. |

Existing endpoints that remain unchanged:
- `POST /api/v1/runtime/start` / `stop` — engine lifecycle.
- `GET /api/v1/runtime/status` — engine health.
- `GET /api/v1/manager/status` — overall manager status.
- `POST /api/v1/runtime/{engine_type}/install` — managed engine installation.
- `POST /api/v1/runtime/{engine_type}/update` — managed engine update.

### 4.3 New Zustand Stores

| Store | Responsibility |
| --- | --- |
| `useNavigationStore` | `activeView` enum, rail collapse state, view history. |
| `useEngineStore` | Engine instance list, status polling, deployment progress state. |
| `useHardwareStore` | GPU stats, polling interval management, popover open state. |
| `useSettingsStore` | Mirror configuration, exit policy preference, general app settings. |

### 4.4 New Frontend Components

| Component | Location | Purpose |
| --- | --- | --- |
| `GlobalNavRail` | `components/navigation/GlobalNavRail.tsx` | Left sidebar icon rail with status badges. |
| `ViewContainer` | `components/navigation/ViewContainer.tsx` | Keep-alive view host that toggles visibility. |
| `LauncherHub` | `components/launcher/LauncherHub.tsx` | Main launcher view with instance card grid. |
| `InstanceCard` | `components/launcher/InstanceCard.tsx` | Individual engine/workspace card component. |
| `DeploymentDrawer` | `components/launcher/DeploymentDrawer.tsx` | Slide-out panel with progress bar and log terminal. |
| `EngineConfigModal` | `components/launcher/EngineConfigModal.tsx` | Engine configuration form (port, args, mirrors). |
| `GpuStatusIndicator` | `components/titlebar/GpuStatusIndicator.tsx` | Compact GPU status in the titlebar with hover popover. |
| `GpuDetailPopover` | `components/titlebar/GpuDetailPopover.tsx` | Expanded GPU stats floating card. |
| `EmbeddedEngineView` | `components/engine/EmbeddedEngineView.tsx` | Iframe wrapper with utility toolbar for ComfyUI/WebUI. |
| `ExitConfirmDialog` | `components/launcher/ExitConfirmDialog.tsx` | Application exit confirmation with "remember" checkbox. |

---

## 5. Interaction Flows

### 5.1 First Launch Flow

```
User opens Berry AI Studio
  → Launcher Hub loads (featherweight, no GPU wait)
  → Background: poll /api/v1/hardware/gpu-stats → populate GPU status bar
  → Background: poll /api/v1/engines/instances → populate instance cards
  → Background: call /api/v1/engines/detect → detect existing local engines
  → If engines detected: show "Found ComfyUI at D:\ComfyUI" notification card
  → User clicks "Infinite Canvas" card or rail icon → switch to canvas view
```

### 5.2 Engine Deployment Flow

```
User clicks "+ New Instance" card
  → Select engine type: ComfyUI or WebUI
  → Configure: installation directory, mirror preset
  → Click "Install"
  → DeploymentDrawer opens with progress bar and live log
  → Backend downloads, extracts, creates venv, installs dependencies
  → On success: new instance card appears with ⚫ Stopped status
  → User clicks "Start" → engine launches → card transitions to 🟢 Running
```

### 5.3 Application Exit Flow

```
User clicks window close [X]
  → Check: are any managed engines running?
  → If no: exit immediately
  → If yes: show ExitConfirmDialog
    → "Close All": stop managed engines, then exit
    → "Keep Running": exit app UI, leave engine processes alive
    → Checkbox "Remember my choice": persist to settings
  → External engines are NEVER affected
```

---

## 6. Constraints & Non-Goals

### Constraints
- **Zero Host Pollution**: All managed engine installations use isolated directories and sandboxed Python environments per [AGENTS.md](../AGENTS.md) invariant #4.
- **No Business Logic Duplication**: The Launcher Hub frontend calls existing backend REST APIs. Engine lifecycle, model scanning, and installation logic remain exclusively in the Python backend per L11.
- **5-Type Port Contract**: The Launcher Hub does not introduce new execution port types. It is a navigation and management layer, not an execution layer.
- **English artifacts**: All code comments, component names, and documentation are in English per project conventions.

### Non-Goals (v1)
- **"Skip launcher" default view preference**: Deferred to a future settings enhancement.
- **Multi-window / detachable views**: Each workspace is embedded within the single Tauri window.
- **Remote engine connections**: Connecting to ComfyUI/WebUI on other machines over the network.
- **Model marketplace or download manager**: Model management remains in the existing Environment Manager modal.
- **Drag-and-drop instance reordering**: Cards use a static grid layout.
