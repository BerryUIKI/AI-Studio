# Berry AI Studio - Hardware & Platform Support Matrix

This document defines the supported discrete GPU hardware, acceleration backends, operating systems, and verification tiers for **Berry AI Studio** local inference and engine execution (M11).

---

## 1. Discrete GPU Tier Classification

| Tier | Definition | Expected Performance | Verification Status |
| :--- | :--- | :--- | :--- |
| **Tier 1: Verified Reference Hardware (Physical Evidence)** | Tested and validated directly on physical hardware rigs with documented generation runs. Native acceleration with FP16 tensor core optimization. | High (SDXL < 5s, Flux < 15s) | **Physically Verified**: NVIDIA GeForce RTX (Ampere/Ada on Windows 11 with CUDA 12.x; verified on RTX 3060 12GB). |
| **Tier 2: Candidate Reference Architecture (Unverified on Physical Hardware)** | Structural detection, launch flags, and DirectML / ROCm / IPEX adapters implemented and tested via mock fixtures. | Moderate (SD1.5 < 4s, SDXL < 15s) | **Candidate Architecture**: AMD Radeon (DirectML/ROCm), Intel Arc (DirectML/OneAPI IPEX). Physical generation unverified in this session. |
| **Tier 3: Source-Compatible Platform (Unverified Native Package)** | Cross-platform code paths (Metal MPS, POSIX sockets, platform launchers) implemented and unit-tested. | Device dependent | **Source Compatible Only**: macOS Apple Silicon, Linux (Ubuntu). Native binary execution and packaging unverified in this session. |
| **Tier 4: Cloud Recommended** | Systems with < 6GB VRAM, legacy architectures (pre-DirectX 12.1), integrated GPUs, or CPU-only setups. | Insufficient for local SDXL/Flux | GUI prompts user to configure Cloud BYOK (OpenAI, Fal.ai, SiliconFlow). |

---

## 2. Hardware Support Matrix

### NVIDIA GeForce & RTX (Native CUDA)
| Hardware | Windows 10/11 | Linux (Ubuntu 22.04+) | Backend | Status |
| :--- | :--- | :--- | :--- | :--- |
| RTX 4090 / 4080 / 4070 (Ada) | Native CUDA | Native CUDA | `cuda` | Compatible (Candidate Architecture) |
| RTX 3090 / 3080 / 3070 / 3060 (Ampere) | Native CUDA | Native CUDA | `cuda` | **Physically Verified on Windows Rig** (RTX 3060 12GB, driver 572.70) |
| RTX 2080 / 2070 / 2060 (Turing) | Native CUDA | Native CUDA | `cuda` | Compatible (Candidate Architecture) |
| GTX 1660 / 1650 (6GB) | Native CUDA | Native CUDA | `cuda` (lowvram) | Supported |
| GTX 1080 / 1070 (Pascal) | Native CUDA | Native CUDA | `cuda` (fp32 fallback) | Supported |

### AMD Radeon (DirectML & ROCm)
| Hardware | Windows 10/11 | Linux (Ubuntu 22.04+) | Backend | Status |
| :--- | :--- | :--- | :--- | :--- |
| Radeon RX 7900 XTX / XT (RDNA3) | DirectML (`--directml`) | ROCm 6.1+ | `directml` / `rocm` | Candidate Reference Architecture (Physical execution unverified) |
| Radeon RX 7800 XT / 7700 XT (RDNA3) | DirectML (`--directml`) | ROCm 6.1+ | `directml` / `rocm` | Candidate Reference Architecture (Physical execution unverified) |
| Radeon RX 6800 XT / 6700 XT (RDNA2) | DirectML (`--directml`) | ROCm 5.7+ | `directml` / `rocm` | Candidate Reference Architecture (Physical execution unverified) |
| Radeon RX 6600 / 6500 XT | DirectML (`--lowvram`) | Community ROCm | `directml` | Experimental |
| Older Radeon RX 5000 / Vega | DirectML | Not recommended | `directml` | Experimental / Cloud Recommended |

### Intel Arc Discrete GPUs
| Hardware | Windows 10/11 | Linux (Ubuntu 22.04+) | Backend | Status |
| :--- | :--- | :--- | :--- | :--- |
| Intel Arc A770 (16GB) | DirectML (`--directml`) | OneAPI IPEX | `directml` / `ipex` | Candidate Reference Architecture (Physical execution unverified) |
| Intel Arc A750 (8GB) | DirectML (`--directml`) | OneAPI IPEX | `directml` / `ipex` | Candidate Reference Architecture (Physical execution unverified) |
| Intel Arc A580 / A380 | DirectML (`--lowvram`) | OneAPI IPEX | `directml` | Experimental |

### Apple Silicon (macOS Metal)
| Hardware | macOS 14+ (Sonoma) | macOS 13 (Ventura) | Backend | Status |
| :--- | :--- | :--- | :--- | :--- |
| Apple M1 / M2 / M3 / M4 (Max / Pro) | Native Metal (MPS) | Native Metal (MPS) | `mps` | Source Compatible (Native build/run unverified) |
| Apple M1 / M2 / M3 (Base 8GB/16GB) | Native Metal (`--lowvram`) | Native Metal (`--lowvram`) | `mps` | Source Compatible (Native build/run unverified) |

---

## 3. Automated Supervisor Launch Flags

Berry AI Studio dynamically detects GPU vendor, compute backend, and available VRAM, automatically injecting the required engine launch arguments:

```bash
# NVIDIA (Default CUDA)
python main.py --port 8188 --listen 127.0.0.1

# AMD Radeon (Windows DirectML)
python main.py --port 8188 --listen 127.0.0.1 --directml --use-split-cross-attention

# Intel Arc (Windows DirectML)
python main.py --port 8188 --listen 127.0.0.1 --directml --use-split-cross-attention

# Low VRAM GPUs (< 6GB)
python main.py --port 8188 --listen 127.0.0.1 --lowvram

# Apple Silicon (Metal)
python main.py --port 8188 --listen 127.0.0.1 --force-fp16
```

---

## 4. Unverified & Unsupported Combinations

If your hardware is classified as Tier 3 or unverified:
1. Open **Cloud BYOK** in the top navigation bar.
2. Enter your API key for **Fal.ai**, **SiliconFlow**, or **OpenAI**.
3. Berry will execute all creative actions (txt2img, img2img, inpaint, upscale, txt2video) through the cloud with zero GPU requirements and instant startup.
