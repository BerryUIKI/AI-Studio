# Berry AI Studio Launcher Hub — Implementation Milestones

Date: 2026-10-03. Status: approved plan; implementation pending.
Parent PRD: [Launcher Hub PRD](LAUNCHER_HUB_PRD.md).
Governing Documents: [Roadmap](ROADMAP.md), [Architecture](ARCHITECTURE.md), [Launcher Requirements L01–L12](LAUNCHER_MANAGER_REQUIREMENTS.md).

---

## Overview

The Launcher Hub implementation is broken into 5 incremental milestones. Each milestone is independently shippable and testable. Dependencies flow strictly downward — later milestones build on earlier ones.

```
LH-M1 (Navigation Shell)
  └─→ LH-M2 (Launcher Hub View & Instance Cards)
        ├─→ LH-M3 (Engine Detection, Binding & Deployment)
        └─→ LH-M4 (GPU Monitoring & System Status)
              └─→ LH-M5 (Polish, Exit Policy & Integration Testing)
```

---

## LH-M1 — Navigation Shell & View Router

**Goal**: Replace the current single-view `App.tsx` with a multi-view architecture using a collapsible left navigation rail and keep-alive view container.

### Deliverables

| # | Task | Files |
| --- | --- | --- |
| 1 | Create `useNavigationStore` with `activeView` enum (`launcher`, `canvas`, `comfyui`, `webui`, `agents`, `settings`) and rail collapse state | `stores/useNavigationStore.ts` |
| 2 | Implement `GlobalNavRail` component: icon-only (56px) vertical sidebar, hover expand to show labels, click to switch views, collapse toggle button | `components/navigation/GlobalNavRail.tsx` |
| 3 | Implement `ViewContainer` component: renders all views simultaneously, toggles `visibility`/`display` based on `activeView`, preserves component state across switches | `components/navigation/ViewContainer.tsx` |
| 4 | Refactor `App.tsx`: wrap existing canvas layout inside `ViewContainer` as the `canvas` view, add `GlobalNavRail` to the left, set initial `activeView` to `launcher` | `App.tsx` |
| 5 | Create placeholder views for `LauncherHub`, `ComfyUIView`, `WebUIView`, `AgentsView`, `SettingsView` | `components/launcher/LauncherHub.tsx`, `components/engine/EmbeddedEngineView.tsx` |

### Acceptance Criteria
- Application opens showing the left rail with the Launcher Hub view active.
- Clicking each rail icon switches the main content area to the corresponding view.
- Switching from Canvas to Launcher and back preserves canvas node positions and zoom state.
- The rail collapses to a narrow icon strip and expands on toggle.

### Estimated Effort
- Frontend: ~2–3 days.
- Backend: none.

---

## LH-M2 — Launcher Hub View & Instance Cards

**Goal**: Build the Launcher Hub landing page with a responsive card grid showing all registered workspaces and engine instances.

### Deliverables

| # | Task | Files |
| --- | --- | --- |
| 1 | Create `useEngineStore` for engine instance list, status polling, and deployment state | `stores/useEngineStore.ts` |
| 2 | Implement `LauncherHub` view: header with search bar, card grid layout (responsive CSS grid, min 280px card width) | `components/launcher/LauncherHub.tsx` |
| 3 | Implement `InstanceCard` component: card shell with icon, name, version, status badge (🟢🔴🟡⚫⚪), primary action button, three-dot menu | `components/launcher/InstanceCard.tsx` |
| 4 | Built-in cards: "Infinite Canvas" (always available, no status needed), "+ New Instance" (add engine) | `components/launcher/InstanceCard.tsx` |
| 5 | Wire `useEngineStore` to poll `GET /api/v1/engines/instances` and `GET /api/v1/runtime/status` for live status updates | `stores/useEngineStore.ts` |
| 6 | Add rail icon status badges: green dot overlay when engine is running, pulse animation during active generation | `components/navigation/GlobalNavRail.tsx` |
| 7 | Backend: implement `GET /api/v1/engines/instances` endpoint returning unified list of managed + external engines with status | `backend/app/main.py` or new router |

### Acceptance Criteria
- Launcher Hub shows a card for each registered engine instance and built-in workspaces.
- Cards display correct live status (polling every 5 seconds).
- Three-dot menu opens with all specified options (non-functional stubs acceptable for Configure, View Logs, Open Directory in this milestone).
- "+ New Instance" card is visible and clickable (opens a placeholder modal).
- Rail icons show green dots for running engines.

### Estimated Effort
- Frontend: ~3–4 days.
- Backend: ~1 day (new endpoint).

---

## LH-M3 — Engine Detection, Binding & Deployment

**Goal**: Enable auto-detection of existing local engines, manual path binding, and managed engine installation with progress UI and mirror acceleration.

### Deliverables

| # | Task | Files |
| --- | --- | --- |
| 1 | Backend: implement `GET /api/v1/engines/detect` — scan common Windows directories for ComfyUI and WebUI installations using heuristics (`main.py` + `comfy/`, `webui-user.bat` + `modules/`) | `backend/app/runtime/engine_manager.py` |
| 2 | Backend: implement `POST /api/v1/engines/bind` — register an external engine directory, validate structure, extract version | `backend/app/runtime/engine_manager.py` |
| 3 | Backend: implement `POST /api/v1/engines/unbind/{id}` — remove external engine binding (no file deletion) | `backend/app/runtime/engine_manager.py` |
| 4 | Backend: implement mirror configuration endpoints `GET/PUT /api/v1/installer/mirrors` with presets (Direct, China Mainland) and custom URL support | `backend/app/runtime/installer.py` |
| 5 | Backend: extend managed installation to respect mirror configuration for git clone, pip install, and model downloads | `backend/app/runtime/installer.py` |
| 6 | Frontend: implement "Add Engine" modal with tabs: "Auto-Detected" (list of found installations), "Browse…" (manual directory picker via Tauri file dialog), "Install New" (managed installation form with mirror selector) | `components/launcher/AddEngineModal.tsx` |
| 7 | Frontend: implement `DeploymentDrawer` — slide-out panel with: progress bar (percentage), current step label, scrolling log terminal (monospace, auto-scroll), cancel button | `components/launcher/DeploymentDrawer.tsx` |
| 8 | Frontend: implement `EngineConfigModal` — form for port number, extra CLI arguments (text input with common presets like `--xformers`, `--lowvram`), mirror selection | `components/launcher/EngineConfigModal.tsx` |
| 9 | Wire three-dot menu actions: Configure → `EngineConfigModal`, View Logs → log viewer, Open Directory → Tauri `shell.open()`, Uninstall/Unbind → confirmation dialog | `components/launcher/InstanceCard.tsx` |

### Auto-Detection Scan Targets (Windows)

```
# ComfyUI detection patterns
%USERPROFILE%\ComfyUI
%USERPROFILE%\Desktop\ComfyUI*
%HOMEDRIVE%\ComfyUI*
%HOMEDRIVE%\ComfyUI_windows_portable*
%HOMEDRIVE%\AI\ComfyUI*

# SD WebUI detection patterns
%USERPROFILE%\stable-diffusion-webui
%USERPROFILE%\Desktop\stable-diffusion-webui*
%HOMEDRIVE%\stable-diffusion-webui*
%HOMEDRIVE%\sd-webui*
%HOMEDRIVE%\秋叶整合包*
%HOMEDRIVE%\A1111*

# Also scan: same drive as Berry installation, common AI tool directories
```

### Mirror Presets

| Preset | Git Clone | pip Index | HuggingFace |
| --- | --- | --- | --- |
| Direct | `github.com` | `pypi.org/simple` | `huggingface.co` |
| China Mainland | `ghproxy.com` or `mirror.ghproxy.com` | `pypi.tuna.tsinghua.edu.cn/simple` or `mirrors.aliyun.com/pypi/simple` | `hf-mirror.com` |
| Custom | User-specified URL | User-specified URL | User-specified URL |

### Acceptance Criteria
- Auto-detection finds ComfyUI/WebUI installations in standard locations.
- Manual browse correctly validates and binds a user-selected directory.
- Managed installation downloads, extracts, and configures a sandboxed engine with real-time progress.
- Mirror selection persists and is applied to all network operations during installation.
- Uninstalling a managed engine removes the sandboxed directory; unbinding an external engine only removes the registration.

### Estimated Effort
- Frontend: ~4–5 days.
- Backend: ~3–4 days.

---

## LH-M4 — GPU Monitoring & System Status

**Goal**: Add real-time GPU/VRAM monitoring to the titlebar and a detailed system status popover.

### Deliverables

| # | Task | Files |
| --- | --- | --- |
| 1 | Backend: implement `GET /api/v1/hardware/gpu-stats` — calls `nvidia-smi --query-gpu=name,driver_version,temperature.gpu,utilization.gpu,memory.total,memory.used,memory.free --format=csv,noheader,nounits` and parses results; returns per-process VRAM via `nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits` cross-referenced with known engine PIDs | `backend/app/runtime/hardware.py` |
| 2 | Create `useHardwareStore` for GPU stats, polling interval (3s normal, 1s when popover open), and popover state | `stores/useHardwareStore.ts` |
| 3 | Implement `GpuStatusIndicator` — compact titlebar widget: `GPU_NAME · USED / TOTAL (%)` with color coding (green < 50%, yellow 50–80%, red > 80%) | `components/titlebar/GpuStatusIndicator.tsx` |
| 4 | Implement `GpuDetailPopover` — hover/click floating card: GPU model, driver version, temperature with icon, utilization bar, VRAM bar, per-process table (Process Name, PID, VRAM) | `components/titlebar/GpuDetailPopover.tsx` |
| 5 | Graceful degradation: when no NVIDIA GPU or `nvidia-smi` unavailable, show "Cloud Mode · No GPU" in titlebar; popover shows guidance text | `components/titlebar/GpuStatusIndicator.tsx` |

### Acceptance Criteria
- GPU status appears in the titlebar on systems with NVIDIA GPUs.
- Hovering shows the detailed popover with temperature, utilization, and per-process breakdown.
- On systems without NVIDIA GPUs, the indicator shows "Cloud Mode" and does not error.
- Polling frequency increases when popover is open and decreases when closed.

### Estimated Effort
- Frontend: ~2 days.
- Backend: ~1 day.

---

## LH-M5 — Polish, Exit Policy & Integration Testing

**Goal**: Implement the application exit confirmation dialog, polish visual design, and run end-to-end integration tests.

### Deliverables

| # | Task | Files |
| --- | --- | --- |
| 1 | Implement `ExitConfirmDialog` — triggered on window close (`beforeunload` or Tauri `close_requested` event) when managed engines are running; "Close All" / "Keep Running" / "Remember" checkbox | `components/launcher/ExitConfirmDialog.tsx` |
| 2 | Implement `useSettingsStore` for persisted user preferences: exit policy, mirror config, rail collapse state | `stores/useSettingsStore.ts` |
| 3 | Wire Tauri `close_requested` event to check managed engine status before allowing window close | `App.tsx` or `main.tsx` |
| 4 | Visual polish: card hover effects, smooth rail collapse animation, status badge transitions, dark theme consistency with existing canvas aesthetic | Various component files |
| 5 | Implement engine log viewer: modal or drawer that streams recent log output from `GET /api/v1/runtime/{engine_id}/logs` | `components/launcher/EngineLogViewer.tsx` |
| 6 | Integration tests: startup → launcher visible, card click → view switch, engine start/stop from launcher, exit dialog behavior | `tests/` |
| 7 | Update Tauri CSP configuration to allow iframe origins for `127.0.0.1:*` (engine webviews) | `frontend/src-tauri/tauri.conf.json` |

### Acceptance Criteria
- Closing the app with running engines shows the confirmation dialog.
- "Remember my choice" persists the preference across app restarts.
- External engines are never mentioned in or affected by the exit dialog.
- All card actions (Configure, View Logs, Open Directory) are fully functional.
- Visual design is consistent with the existing Berry AI Studio dark theme.
- Navigation between all views is smooth with no flickering or state loss.

### Estimated Effort
- Frontend: ~3–4 days.
- Backend: ~1 day (log streaming endpoint).
- Testing: ~2 days.

---

## Summary Timeline

| Milestone | Duration Estimate | Cumulative |
| --- | --- | --- |
| **LH-M1**: Navigation Shell & View Router | 2–3 days | Week 1 |
| **LH-M2**: Launcher Hub View & Instance Cards | 4–5 days | Week 1–2 |
| **LH-M3**: Engine Detection, Binding & Deployment | 7–9 days | Week 2–3 |
| **LH-M4**: GPU Monitoring & System Status | 3 days | Week 3–4 |
| **LH-M5**: Polish, Exit Policy & Integration Testing | 5–7 days | Week 4–5 |
| **Total** | **~21–27 working days (~4–5 weeks)** | |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Tauri CSP blocks iframe embedding of local engine web UIs | Medium | High | Test early in LH-M1; fall back to `tauri::WebviewUrl` or system browser launch if CSP cannot be resolved. |
| Keep-alive views consume excessive memory with multiple engine iframes loaded | Medium | Medium | Lazy-load engine iframes only when first navigated to; unload after configurable idle timeout. |
| `nvidia-smi` parsing fragility across driver versions | Low | Medium | Use structured CSV output format; fall back gracefully on parse errors. |
| Auto-detection false positives (non-engine directories matching heuristics) | Low | Low | Always require user confirmation before binding a detected path. |
| Mirror URLs become stale or unreachable | Medium | Low | Allow user-specified custom mirrors; provide a "test connection" button in settings. |

---

## Relationship to Existing Milestones

This Launcher Hub work extends and refines the existing **M6 (Rust Launcher and Environment Manager)** milestone defined in [ROADMAP.md](ROADMAP.md). Specifically:

- **M6 L01–L03** (entry point, startup, single instance): Already implemented in the Rust launcher. The Launcher Hub adds the **frontend GUI** experience on top of the existing Rust bootstrap.
- **M6 L04** (clear status): The Launcher Hub instance cards and GPU monitor fulfill this requirement with a richer UI than the current `EnvironmentManagerModal`.
- **M6 L05** (controlled engines): Instance cards with start/stop/install/configure actions provide the user-facing controls. Backend APIs already exist.
- **M6 L07** (shutdown policy): The `ExitConfirmDialog` directly implements this requirement.
- **M6 L08** (updates): Cards show version and update availability; three-dot menu provides update actions.
- **M6 L10** (model inventory): Model management remains in the existing Environment Manager, accessible from the Settings view or a dedicated future model manager view.

The Launcher Hub does NOT replace the Rust launcher binary. The Rust launcher (`berry.exe`) continues to own process bootstrap, single-instance enforcement, backend process supervision, and CLI commands. The Launcher Hub is the **React frontend view** that the user sees after bootstrap completes.
