# Berry AI Studio - Hardware & Platform Support Matrix

This document defines the supported discrete GPU hardware, acceleration backends, operating systems, and verification tiers for **Berry AI Studio** local inference and engine execution (M11).

---

## 1. Verification Status Taxonomy

Berry AI Studio strictly distinguishes four distinct verification tiers across all documentation, tests, and user-facing reports:

| Status | Exact Definition | Scope in Berry AI Studio |
| :--- | :--- | :--- |
| **Physical Hardware Verification** | Executed and confirmed on a physical host machine with documented hardware, drivers, and real generation outputs. | **Windows 11 (x86_64) with NVIDIA GeForce RTX 3060 12GB (Ampere)**, NVIDIA Driver 572.70, CUDA 12.8. Real ComfyUI local inference verified. |
| **Mocked Verification** | Logic, detection, flags, and schemas verified via automated unit/integration tests using mocked I/O, simulated WMI controllers, or mock subprocess responses. | **AMD Radeon (DirectML/ROCm)**, **Intel Arc (DirectML/OneAPI IPEX)**, DAG cycle detection, hash caching, engine process supervisor state machines. |
| **Source Compatibility** | Platform adapters, path normalization, browser spawn commands, and single-instance locks implemented and passing unit tests, without native packaging or physical execution on native OS machines. | **macOS (Apple Silicon Metal MPS)**, **Linux (Ubuntu 22.04+)**. Source code is portable; native runtime binaries and desktop execution unverified in this session. |
| **Real Provider Verification** | Live network API requests executed against remote cloud infrastructure using authenticated user BYOK credentials. | **Fal.ai** (FLUX Schnell), **SiliconFlow**, and **OpenAI** (DALL-E) verified via real API calls. Advanced video models (Fal SVD, CogVideoX) require funded BYOK keys and are verified via contract schema checks. |

---

## 2. Hardware Support & Verification Matrix

### NVIDIA GeForce & RTX (Native CUDA)
| Hardware | Windows 10/11 | Linux (Ubuntu 22.04+) | Backend | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| RTX 3060 12GB (Ampere) | Native CUDA | Native CUDA | `cuda` | **Physical Hardware Verified** (Host rig: Driver 572.70, CUDA 12.8) |
| RTX 4090 / 4080 / 4070 (Ada) | Native CUDA | Native CUDA | `cuda` | Mocked Verification (Candidate Architecture) |
| RTX 3090 / 3080 / 3070 (Ampere) | Native CUDA | Native CUDA | `cuda` | Mocked Verification (Candidate Architecture) |
| RTX 2080 / 2070 / 2060 (Turing) | Native CUDA | Native CUDA | `cuda` | Mocked Verification (Candidate Architecture) |
| GTX 1660 / 1650 (6GB) | Native CUDA | Native CUDA | `cuda` (lowvram) | Mocked Verification (Candidate Architecture) |
| GTX 1080 / 1070 (Pascal) | Native CUDA | Native CUDA | `cuda` (fp32 fallback) | Mocked Verification (Candidate Architecture) |

### AMD Radeon (DirectML & ROCm)
| Hardware | Windows 10/11 | Linux (Ubuntu 22.04+) | Backend | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| Radeon RX 7900 XTX / XT (RDNA3) | DirectML (`--directml`) | ROCm 6.1+ | `directml` / `rocm` | Mocked Verification (Candidate Architecture; unverified physical hardware) |
| Radeon RX 7800 XT / 7700 XT (RDNA3) | DirectML (`--directml`) | ROCm 6.1+ | `directml` / `rocm` | Mocked Verification (Candidate Architecture; unverified physical hardware) |
| Radeon RX 6800 XT / 6700 XT (RDNA2) | DirectML (`--directml`) | ROCm 5.7+ | `directml` / `rocm` | Mocked Verification (Candidate Architecture; unverified physical hardware) |
| Radeon RX 6600 / 6500 XT | DirectML (`--lowvram`) | Community ROCm | `directml` | Experimental (Unverified physical hardware) |
| Older Radeon RX 5000 / Vega | DirectML | Not recommended | `directml` | Experimental / Cloud Recommended |

### Intel Arc Discrete GPUs
| Hardware | Windows 10/11 | Linux (Ubuntu 22.04+) | Backend | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| Intel Arc A770 (16GB) | DirectML (`--directml`) | OneAPI IPEX | `directml` / `ipex` | Mocked Verification (Candidate Architecture; unverified physical hardware) |
| Intel Arc A750 (8GB) | DirectML (`--directml`) | OneAPI IPEX | `directml` / `ipex` | Mocked Verification (Candidate Architecture; unverified physical hardware) |
| Intel Arc A580 / A380 | DirectML (`--lowvram`) | OneAPI IPEX | `directml` | Experimental (Unverified physical hardware) |

### Apple Silicon (macOS Metal)
| Hardware | macOS 14+ (Sonoma) | macOS 13 (Ventura) | Backend | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| Apple M1 / M2 / M3 / M4 (Max / Pro) | Native Metal (MPS) | Native Metal (MPS) | `mps` | Source Compatibility (Native build/run unverified) |
| Apple M1 / M2 / M3 (Base 8GB/16GB) | Native Metal (`--lowvram`) | Native Metal (`--lowvram`) | `mps` | Source Compatibility (Native build/run unverified) |

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
