# Berry AI Studio User Guide & Quickstart

Welcome to **Berry AI Studio**, the beginner-friendly creative workspace with an infinite canvas for AI image creation.

---

## 1. Quick Start on Windows

### Prerequisites
- Windows 10 or 11 (64-bit).
- Python 3.10 or higher installed from [python.org](https://python.org) (ensure *"Add python.exe to PATH"* is checked during installation).

### Launching Berry
1. Double-click `scripts\launch.bat` (or run `powershell -ExecutionPolicy Bypass -File scripts\start-berry.ps1`).
2. The launcher will automatically configure an isolated development environment in `backend\.venv` if not already present.
3. Your default browser will open automatically to `http://127.0.0.1:8000`.

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
  - Click the engine power button in the header to start Berry's sandboxed local runtime.
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

## 4. Troubleshooting & FAQ

- **Backend says "Connecting..."**: Make sure `scripts\launch.bat` is running in a terminal window.
- **"No API key configured" in Cloud Mode**: Click **"Cloud BYOK"** in the header, paste your key from OpenAI/Fal.ai/SiliconFlow, and click **"Save"**.
- **Can I add my own local model checkpoints?**: Yes! Berry scans `%LOCALAPPDATA%\AI-Workflow\engine\models\checkpoints` and lets you add custom directories via the Model Manager API.
