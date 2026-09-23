# Berry AI Studio Support Matrix & Environment Baseline

Release Version: **0.1.0**  
Date: **2026-09-23**  
Target Platform: **Windows 10 / 11 (64-bit)** with portable core architecture.

---

## 1. Operating Systems & Hardware

| Environment | Supported Tier | Notes & Requirements |
| --- | --- | --- |
| **Windows 11 / 10 (64-bit)** | **Primary Supported** | Recommended release target. Tested with PowerShell and Batch launch scripts. |
| **NVIDIA GPU (>= 12GB VRAM)** | **Full Local Inference** | SDXL, Flux Schnell/Dev, SD 1.5, inpainting, and 4x upscaling supported locally. |
| **NVIDIA GPU (6GB – 12GB VRAM)**| **Standard Local Inference** | SD 1.5 and SDXL supported locally. Flux recommended with low-vram offload. |
| **NVIDIA GPU (< 6GB VRAM)** | **Limited Local / Low-VRAM** | SD 1.5 supported in low-vram mode; cloud API inference recommended for large models. |
| **No Discrete NVIDIA GPU** | **Cloud-Only Supported** | Runs full Berry UI and creative canvas via BYOK cloud APIs. Zero torch or CUDA required. |
| **macOS / Linux** | **Portable Core (Dev Only)** | Core backend & frontend pass automated suites; native desktop packaging deferred to later releases. |

---

## 2. Local Engine Support

| Local Engine | Minimum Tested Version | Integration Mode | Ownership Contract |
| --- | --- | --- | --- |
| **ComfyUI** | `v0.2.0+` (latest API) | Managed (Supervisor) or External | Isolated venv in `%LOCALAPPDATA%\AI-Workflow\engine\runtime\`. External engines remain unmutated (zero process killing). |
| **Stable Diffusion WebUI** | `v1.10.0+` (`--api`) | Managed (Supervisor) or External | Dedicated venv in `%LOCALAPPDATA%\AI-Workflow\engine\webui_runtime\`. Connects to `/sdapi/v1/*`. |

---

## 3. Supported Model Architectures

| Architecture | Model Family | Formats | Category | Tested Dependencies |
| --- | --- | --- | --- | --- |
| **SDXL** | Stable Diffusion XL Base 1.0 | `.safetensors`, `.ckpt` | Checkpoint | Built-in VAE; operates optimally at 1024×1024. |
| **SD 1.5** | v1-5-pruned-emaonly | `.safetensors`, `.ckpt` | Checkpoint | Baseline 512×512 resolution. |
| **Flux** | FLUX.1 [schnell] / [dev] | `.safetensors` | Checkpoint / UNet | Requires external CLIP-L, T5-XXL, and VAE if unbundled. |
| **LoRA** | SD 1.5 & SDXL LoRA adapters | `.safetensors` | LoRA | Injected dynamically into model and CLIP streams. |
| **Upscalers** | RealESRGAN_x4plus, 4x-UltraSharp | `.pth` | Upscaler | 2× and 4× super-resolution models. |

---

## 4. BYOK Cloud Providers

| Provider | Supported Models | Capabilities | Upload / Billing Notes |
| --- | --- | --- | --- |
| **OpenAI** | DALL-E 3, GPT-4o | `txt2img` | Prompts processed on OpenAI cloud. Billed directly to user's OpenAI account. |
| **Fal.ai** | FLUX.1 [schnell], FLUX.1 [dev] | `txt2img`, `img2img` | Serverless GPU execution. Low latency; billed to user's Fal.ai key. |
| **SiliconFlow** | SDXL Turbo, SD 3.5 Large | `txt2img` | High-throughput cloud inference endpoints. Billed to user's SiliconFlow account. |

---

## 5. Storage & Isolation Safeguards

- **Backend Core**: Does not import or depend on PyTorch or CUDA libraries. Boots in < 2 seconds.
- **Engine Isolation**: Sandboxed virtual environments only. Never runs global `pip install` commands.
- **Credential Storage**: Stored locally in `%LOCALAPPDATA%\BerryAIStudio\credentials.json`. Strictly redacted from logs, exports, and status endpoints.
- **Asset Adoption**: All remote images (from cloud providers or ComfyUI `/view`) are immediately persisted locally in content-addressable storage (`assets/{hash[:2]}/{hash}.png`).

---

## 6. Packaging & Entry Points: Release vs Development Fallback

| Flow | Target Audience | Prerequisites | Launch Mechanism | Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Distributed Windows Package** | End users / Clean machines | **Zero** (no host Python, no Node.js, no Git) | `berry.exe` (Rust binary) | Uses embedded Python in `runtime/python/` and pre-built frontend in `frontend/dist/`. 100% self-contained. |
| **Source Developer Checkout** | Contributors / Developers | Python 3.10+, Node.js (pnpm), Rust/Cargo | `scripts\launch.bat` or `scripts\start-berry.ps1` | Creates developer `backend/.venv` using host Python; runs Vite/backend directly; checks frontend build readiness. |
