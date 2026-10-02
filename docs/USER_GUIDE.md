# Berry AI Studio User Guide & Quickstart

Welcome to **Berry AI Studio**, the beginner-friendly creative workspace with an infinite canvas for AI image creation.

---

## 1. Quick Start on Windows

### Prerequisites
- Windows 10 or 11 (64-bit).
- Python 3.10 or higher installed from [python.org](https://python.org) (ensure *"Add python.exe to PATH"* is checked during installation).

### Launching Berry
1. Double-click `scripts\launch.bat` (or run `powershell -ExecutionPolicy Bypass -File scripts\start-berry.ps1`).
2. Alternatively, run the high-performance Rust launcher binary directly:
   ```cmd
   launcher\target\release\berry.exe
   ```
3. The launcher performs automated 4-stage readiness checks, bootstraps isolated environments if needed, and opens your default web browser to `http://127.0.0.1:8000` once the service is confirmed healthy.

---

## 2. Choosing Your Creation Mode

Berry AI Studio supports two modes of creation:

### Mode A: Cloud-Only (Zero GPU Required)
- **Who it is for**: Users on laptops, office computers, or systems without an NVIDIA GPU.
- **How it works**:
  1. Click **"Cloud BYOK"** in the top header.
  2. Enter an API key for **OpenAI**, **Fal.ai**, or **SiliconFlow**.
  3. Click **"Test Connection"** to verify that your key is active.
  4. Select **"Cloud API (Zero GPU)"** from the creation dock at the bottom of the canvas.
  5. Type a prompt and click **"Generate"**. Images appear directly on your canvas and are automatically saved to your local storage.

### Mode B: Local NVIDIA Acceleration
- **Who it is for**: Users with an NVIDIA GeForce RTX GPU (6GB+ VRAM recommended).
- **Using an Existing Engine**:
  - If you already run ComfyUI (port `8188`) or SD WebUI (port `7860`), Berry detects them automatically and connects with **zero process interference**.
- **Using Berry's Managed Engine**:
  - Open the **"Environment"** manager from the top header to inspect or start Berry's sandboxed local runtimes.
  - All local packages live strictly inside isolated directories (`%LOCALAPPDATA%\AI-Workflow\engine\`) with zero pollution of your system Python.

---

## 3. The Creative Canvas Workflow

You never need to wire nodes to create images in Berry:

1. **Text to Image**: Type a description into the bottom dock (e.g., *"A cozy wooden cabin during sunset, oil painting"*) and select an aspect ratio (`1:1`, `16:9`, `9:16`, `4:3`). Click **"Generate"**.
2. **Contextual Action Bar**: Hover over or select any image on the canvas to reveal quick actions:
   - **Vary (Img2Img)** (✨): Uses the selected image as a reference to produce variations.
   - **Inpaint** (🖌️): Opens the interactive mask painter. Draw white brush strokes over the area you want to replace, describe what should be there, and generate.
   - **Upscale** (🔍): Upscales resolution by 2× or 4× using RealESRGAN.
   - **Export** (📥): Downloads the full-resolution PNG file to your computer.
   - **Remove** (🗑️): Removes the item from the canvas without deleting the source file from your library.
3. **Import Image**: Click **"Import Image"** in the top header to upload any local image onto the canvas.
4. **Power User Node View**: Click **"Nodes"** in the header to toggle the advanced node palette if you wish to inspect or build modular node flows.

---

## 4. Environment Manager & CLI Operations

The Berry launcher (`berry.exe`) remains available as a unified CLI and GUI environment manager:

### CLI Commands
| Command | Description |
| :--- | :--- |
| `berry` | Launch or focus active Berry workspace (no duplicate processes) |
| `berry manager` | Open the Environment Manager view directly |
| `berry status` | Show unified status of core PID, managed engines, cloud, and models |
| `berry stop [--force]` | Controlled shutdown with active task protection |
| `berry models list` | List all discovered models across registered roots |
| `berry models rescan` | Trigger file inspection across all scan roots |
| `berry models roots` | List all registered model directory roots |
| `berry models add-root <dir> <label>` | Register a custom model directory |
| `berry models remove-root <root_id>` | Remove directory from catalog without deleting files |
| `berry engine start <comfyui\|webui>` | Start an isolated managed engine |
| `berry engine stop <comfyui\|webui>` | Stop an isolated managed engine |
| `berry engine update <comfyui\|webui>` | Safe engine update with automatic rollback to previous git commit |
| `berry update check` | Check Berry app and engine updates separately |
| `berry update app` | Trigger Berry application update (git pull in dev; package link in release) |
| `berry update engine <comfyui\|webui>` | Update specified engine runtime |

### Graphical Environment Manager
Access the Environment Manager anytime:
- Click **"Environment"** in the top navigation bar.
- Or click **"Models ↗"** directly inside the bottom creative dock to jump straight to your local model catalog.

The modal features four dedicated panels:
- **Core & Process**: PID, uptime, active tasks counter, and safe **Exit Berry** action.
- **Engines Lifecycle**: Status badges, Start/Stop/Install/Update controls, and external engine links.
- **Model Inventory**: Filterable table of local models, engine compatibility tags, missing dependencies detection, and scan root management (Add/Remove roots non-destructively).
- **Updates & Recovery**: Separate app vs engine updates with rollback state display.

---

## 5. Troubleshooting & FAQ

- **Backend says "Connecting..."**: Make sure `scripts\launch.bat` or `berry.exe` is running.
- **Port 8000 Conflict**: If another application occupies port 8000, Berry launcher outputs an actionable diagnostic message. You can specify a custom port: `set BERRY_PORT=8001 && berry`.
- **Frontend Packaging Diagnostic Page**: If `frontend/dist` has not been built, visiting `http://127.0.0.1:8000` presents an informative HTML diagnostic page rather than a blank 404. Run `cd frontend && pnpm build` to compile the web bundle.
- **"No API key configured" in Cloud Mode**: Click **"Cloud BYOK"** in the header, paste your key from OpenAI/Fal.ai/SiliconFlow, and click **"Save"**.
- **Model Files Safety**: Adding or removing directories in Berry's model inventory is non-destructive and never deletes weights from your disk.
- **Interrupted Engine Update Recovery**: If an engine update fails or is interrupted, the manager automatically checks out the prior git commit and preserves your model files. If third-party pip dependencies inside the engine's isolated virtualenv were damaged, recovery requires clicking "Reinstall" in the Environment Manager or restoring an external backup.
