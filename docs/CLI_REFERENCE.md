# Berry AI Studio - Unified Command-Line Interface (CLI) Reference

The Berry AI Studio CLI provides headless, scriptable, and programmatic access to creative workflows, process supervision, engine lifecycle, task management, and system diagnostics. The CLI is embedded in the Rust launcher executable (`berry.exe` on Windows, `berry` on Linux/macOS) and communicates directly with the Berry Core backend over localhost loopback HTTP REST and WebSocket APIs.

---

## 1. Quick Start

Ensure the Berry backend is running or launch it via the supervisor:
```bash
# Launch GUI workspace and environment supervisor
berry

# Check status of core, engines, and model catalog
berry status

# Check hardware and system diagnostics
berry system
```

---

## 2. Global Options and Environment Variables

| Option / Variable | Description | Default |
| :--- | :--- | :--- |
| `BERRY_PORT` | Custom port for Berry AI Studio backend HTTP server | `8000` |
| `--json` | Format output as structured JSON for automation and scripts | `false` |
| `--help`, `-h` | Display command syntax and available subcommands | - |

Exit Codes:
- `0`: Success
- `1`: Error (validation failure, connectivity issue, or engine execution error)

---

## 3. Creative Workflow Execution (`berry run`)

Executes high-level creative actions directly against local engines (ComfyUI / WebUI) or configured cloud BYOK providers (Fal.ai, SiliconFlow). Supports automatic image/mask uploading, deterministic caching, and output downloading.

### Syntax
```bash
berry run <action> [options]
```

### Supported Actions
- `txt2img`: Text-to-image generation
- `img2img`: Image-to-image styling and transformation
- `inpaint`: Mask-based image editing and replacement
- `upscale`: Image upscaling and resolution enhancement
- `txt2video`: Text-to-video generation (e.g. CogVideoX / AnimateDiff)
- `img2video`: Image-to-video animation (e.g. SVD XT / Fast SVD)

### Command Options
| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--prompt <text>` | String | `""` | Positive prompt describing the desired generation |
| `--negative-prompt <text>` | String | Default negative | Negative prompt describing unwanted attributes |
| `--engine <id>` | String | `managed_comfyui` | Target engine: `managed_comfyui`, `managed_webui`, `fal_ai`, `siliconflow` |
| `--model <name>` | String | `v1-5-pruned-emaonly.safetensors` | Checkpoint or cloud model identifier |
| `--aspect-ratio <ratio>` | String | `1:1` | Aspect ratio: `1:1`, `16:9`, `9:16`, `4:3`, `3:4` |
| `--seed <int>` | Integer | `-1` | Random seed (`-1` for randomized generation) |
| `--steps <int>` | Integer | `20` | Denoising inference steps |
| `--cfg <float>` | Float | `7.0` | Classifier-Free Guidance (CFG) scale |
| `--denoise <float>` | Float | `0.75` | Denoise strength for `img2img` and `inpaint` |
| `--image <file>` | Path | None | Path to local input image for `img2img`, `inpaint`, `upscale`, or `img2video` |
| `--mask <file>` | Path | None | Path to local mask image for `inpaint` |
| `--fps <int>` | Integer | `16` | Video framerate (frames per second) |
| `--frames <int>` | Integer | `25` | Total number of video frames to generate |
| `--motion <int>` | Integer | `127` | Motion bucket ID / intensity for video animation |
| `--upscale-factor <float>` | Float | `2.0` | Scale multiplier for `upscale` action |
| `--output <file>` | Path | None | Destination path to automatically download and save the resulting media file |
| `--json` | Flag | False | Output result as structured JSON to stdout |

### Examples

#### Text-to-Image Generation
```bash
berry run txt2img \
  --prompt "A retro sci-fi rover exploring a neon crater on Mars" \
  --aspect-ratio 16:9 \
  --steps 25 \
  --output ./mars_rover.png
```

#### Image-to-Video Animation
```bash
berry run img2video \
  --image ./mars_rover.png \
  --fps 24 \
  --frames 49 \
  --motion 150 \
  --output ./mars_rover.mp4
```

#### JSON Pipeline Integration
```bash
berry run txt2img --prompt "cyberpunk street market" --json | jq .image_url
```

---

## 4. Task Management (`berry tasks`)

Inspect and cancel background generation and workflow tasks.

### Syntax
```bash
# List all in-flight tasks
berry tasks list [--json]

# Cancel an active task by task ID
berry tasks cancel <task_id> [--json]
```

### Examples
```bash
berry tasks list
# Active Creative Tasks:
#   - Task [c997ff97-15ef-4573-8efd-bb74b09e44eb] : action=txt2video, engine=managed_comfyui

berry tasks cancel c997ff97-15ef-4573-8efd-bb74b09e44eb
# [OK] Task cancellation signal sent for c997ff97-15ef-4573-8efd-bb74b09e44eb
```

---

## 5. System Diagnostics (`berry system`)

Queries hardware readiness, discrete GPU detection, CUDA / ROCm / DirectML availability, memory capacity, and running engine endpoints.

### Syntax
```bash
berry system [--json]
```

---

## 6. Engine and Environment Lifecycle

| Command | Description |
| :--- | :--- |
| `berry status` | Unified status of Berry Core, local managed runtimes, external engines, and model index |
| `berry stop [--force]` | Graceful or forced shutdown of core and child engine processes |
| `berry manager` | Launch or focus the web-based Environment Manager |
| `berry engine start <comfyui\|webui>` | Start managed engine subprocess |
| `berry engine stop <comfyui\|webui>` | Stop managed engine subprocess |
| `berry engine install <comfyui\|webui>` | Initiate isolated engine installation |
| `berry engine update <comfyui\|webui>` | Update engine Git repository with dirty-check & rollback protection |

---

## 7. Model Inventory Management (`berry models`)

| Command | Description |
| :--- | :--- |
| `berry models list` | List indexed models, architecture, file size, and paths |
| `berry models rescan` | Trigger filesystem rescan across all registered model roots |
| `berry models roots` | Display configured model storage roots |
| `berry models add-root <path> <label>` | Add a new model root directory |
| `berry models remove-root <root_id>` | Remove a registered model root directory |

---

## 8. Updates (`berry update`)

| Command | Description |
| :--- | :--- |
| `berry update check` | Check for updates to Berry Studio and managed engines |
| `berry update app` | Update Berry application core |
| `berry update engine <comfyui\|webui>` | Update specified engine |
