# Berry AI Studio Model Hub — UI & Component Specification

Date: 2026-10-03  
Status: Approved UI Design Specification  
Target Version: v0.2.0  
Governing Documents: [`docs/MODEL_HUB_PRD.md`](MODEL_HUB_PRD.md), [`docs/LAUNCHER_HUB_UI_SPEC.md`](LAUNCHER_HUB_UI_SPEC.md).

---

## 1. Global Navigation Rail Entry Point

On the 56px collapsible `GlobalNavRail`, a new top-level icon entry is added:

```
┌──────┐
│  🚀  │  Launcher Hub
│  🎨  │  Infinite Canvas
│  📦  │  Model Hub (NEW)
│  🧩  │  ComfyUI (when active)
│  🔮  │  WebUI (when active)
│  🤖  │  AI Agents
│      │
│  ⚙️  │  Settings
└──────┘
```

- **Icon**: `Package` or `Boxes` from `lucide-react`.
- **Tooltip**: "Model Hub & Downloads"
- **Badge**: Displays total active background downloads count (e.g. `2`).

---

## 2. Model Hub Main Layout Wireframe

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  📦 Model Hub                    [ 🔍 Search models, artists, tags... ]   [⬇️ 2 Tasks]  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Categories:  [ All ]  [ Checkpoints ]  [ LoRAs ]  [ ControlNet ]  [ Upscalers ]       │
│  Base Model:  [ All Architectures ▼ ]   [ Only Compatible With My GPU ☑ ]              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────────┐  │
│  │ ┌───────────────────┐ │  │ ┌───────────────────┐ │  │ ┌───────────────────────┐ │  │
│  │ │                   │ │  │ │                   │ │  │ │                       │ │  │
│  │ │   Preview Image   │ │  │ │   Preview Image   │ │  │ │     Preview Image     │ │  │
│  │ │                   │ │  │ │                   │ │  │ │                       │ │  │
│  │ └───────────────────┘ │  │ └───────────────────┘ │  │ └───────────────────────┘ │  │
│  │ FLUX.1 [schnell] FP8  │  │ SDXL Turbo 1.0        │  │ SD 1.5 Photoreal Classic  │  │
│  │ 11.9 GB · 12B · FP8   │  │ 6.9 GB · 3.5B · FP16  │  │ 2.1 GB · 1.5B · FP16      │  │
│  │ 🟢 Optimal (4-8s/img) │  │ 🟢 Optimal (1-2s/img) │  │ 🟢 Optimal (<1s/img)      │  │
│  │ [ ⬇️ Install (Comfy) ] │  │ [ ⬇️ Install ]         │  │ [ Installed  ✓ ]          │  │
│  └───────────────────────┘  └───────────────────────┘  └───────────────────────────┘  │
│                                                                                        │
│  ┌───────────────────────┐  ┌───────────────────────┐                                  │
│  │ ┌───────────────────┐ │  │ ┌───────────────────┐ │                                  │
│  │ │                   │ │  │ │                   │ │                                  │
│  │ │   Preview Image   │ │  │ │   Preview Image   │ │                                  │
│  │ └───────────────────┘ │  │ └───────────────────┘ │                                  │
│  │ FLUX.1 [dev] FP16     │  │ Wan2.1 14B Video      │                                  │
│  │ 23.8 GB · 12B · FP16  │  │ 14.2 GB · Video       │                                  │
│  │ 🟡 Playable (RAM Swap)│  │ 🔴 OOM Risk (Needs 24G│                                  │
│  │ [ ⬇️ Install (Offload)]│  │ [ ☁️ Use Cloud Model ]│                                  │
│  └───────────────────────┘  └───────────────────────┘                                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Hardware Compatibility Badge & Diagnostic Tooltip

### 3.1 Badge Appearance

| Status | Badge Classes | Example Text |
| :--- | :--- | :--- |
| **Optimal** | `bg-emerald-500/15 text-emerald-300 border-emerald-500/30` | `🟢 Optimal (~4s)` |
| **Playable** | `bg-amber-500/15 text-amber-300 border-amber-500/30` | `🟡 RAM Offload (~18s)` |
| **Heavy Paging** | `bg-orange-500/15 text-orange-300 border-orange-500/30` | `🟠 Heavy Paging (>45s)` |
| **Unsupported** | `bg-rose-500/15 text-rose-300 border-rose-500/30` | `🔴 OOM Risk (Cloud Rec.)` |

### 3.2 Hover Diagnostic Tooltip Wireframe

```
┌────────────────────────────────────────────────────────┐
│  Hardware Compatibility Analysis                       │
├────────────────────────────────────────────────────────┤
│  Model Requirement:                                    │
│  • Memory Footprint:  11.9 GB weights + 2.5 GB buffer  │
│  • Recommended VRAM:  16.0 GB                          │
│  • Minimum VRAM:      8.0 GB                           │
│                                                        │
│  Your System Specs:                                    │
│  • GPU: NVIDIA GeForce RTX 4070 (12.0 GB VRAM)         │
│  • Available VRAM:    10.8 GB                          │
│  • System RAM:        32.0 GB (18.4 GB Available)      │
│                                                        │
│  Diagnosis:                                            │
│  🟢 Optimal VRAM: Model fits comfortably in memory.    │
│  Expected Generation Latency: 4~7 seconds per 1024px. │
└────────────────────────────────────────────────────────┘
```

---

## 4. Download Drawer & Floating Indicator

### 4.1 Floating Indicator (Bottom Right)
When any download task is active, a floating glass pill appears fixed above the canvas/hub:

```
[ ⬇️ 2 Models Downloading · 38.4 MB/s · 2m 14s left  ⌃ ]
```
- Click triggers the slide-out **Download Manager Drawer**.

### 4.2 Download Manager Drawer Wireframe

```
┌─────────────────────────────────────────────────────────────┐
│  Downloads (2 Active, 1 Completed)                       ✕  │
├─────────────────────────────────────────────────────────────┤
│  FLUX.1 [schnell] FP8                                       │
│  Target: ComfyUI (models/checkpoints/)                      │
│  ████████████████░░░░░░░░░░░░░░░░  54% · 6.4 GB / 11.9 GB   │
│  Speed: 38.4 MB/s · Source: hf-mirror.com · ETA: 2m 14s     │
│  [ ⏸ Pause ]  [ ✕ Cancel ]                                │
├─────────────────────────────────────────────────────────────┤
│  SDXL 4x-UltraSharp Upscaler                                │
│  Target: ComfyUI (models/upscale_models/)                   │
│  ██████████████████████████░░░░░░  82% · 54 MB / 66 MB      │
│  Speed: 12.1 MB/s · Source: ModelScope · ETA: 1s            │
│  [ ⏸ Pause ]  [ ✕ Cancel ]                                │
├─────────────────────────────────────────────────────────────┤
│  ✓ SD 1.5 Realistic Vision v5.1                             │
│  Installed to ComfyUI (models/checkpoints/) · 2.1 GB        │
│  [ 📁 Open Folder ]  [ 🗑️ Delete File ]                     │
└─────────────────────────────────────────────────────────────┘
```
