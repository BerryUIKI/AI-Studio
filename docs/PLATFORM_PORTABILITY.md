# Berry AI Studio - Platform Portability & Cross-Platform Architecture (M12)

Berry AI Studio is architected as an API-first, lightweight creative workspace designed to run seamlessly across Windows 10/11, macOS (Apple Silicon), and Linux (Ubuntu 22.04+).

---

## 1. Operating System Directory Conventions

The application maintains zero host environment pollution by isolating managed runtimes, process identifiers, models, and outputs in hermetic directories:

| Component | Windows 10 / 11 | macOS (Apple Silicon / Intel) | Linux (Ubuntu / Debian / Fedora) |
| :--- | :--- | :--- | :--- |
| **Engine Root** | `%LOCALAPPDATA%\AI-Workflow\engine\` | `~/.ai-workflow/engine/` | `~/.ai-workflow/engine/` |
| **Hermetic Python** | `...\engine\runtime\python\Scripts\python.exe` | `.../engine/runtime/python/bin/python` | `.../engine/runtime/python/bin/python` |
| **ComfyUI Checkout** | `...\engine\comfyui\` | `.../engine/comfyui/` | `.../engine/comfyui/` |
| **Model Catalog** | `...\engine\models\` | `.../engine/models/` | `.../engine/models/` |
| **Lock / Socket** | Windows Named Mutex (`Global\BerryAIStudio...`) | Domain Socket (`/tmp/BerryAIStudio...sock`) | Domain Socket (`/tmp/BerryAIStudio...sock`) |

---

## 2. Process Supervision & Single-Instance Locking

### Windows (L03)
- **Single-Instance Mutex**: Utilizes the Win32 `CreateMutexW` API with named mutex `Global\BerryAIStudioLauncherMutex`.
- **Browser Launch**: Spawns `cmd /c start "" <url>`.
- **Process Termination**: Supervises PID with `OpenProcess` / `TerminateProcess`.

### macOS & Linux (M12)
- **Single-Instance Mutex**: Uses Unix domain sockets (`std::os::unix::net::UnixListener`) bound in `$TMPDIR` or `/tmp/`. If a socket already exists, the launcher attempts a non-blocking connection. If active, it focuses the existing workspace; if stale (previous crash), it cleans the socket and rebinds cleanly.
- **Browser Launch**:
  - macOS: Spawns `open <url>`
  - Linux: Spawns `xdg-open <url>`
- **Process Termination**: Supervises PID with POSIX `kill(pid, 0)` and `SIGTERM` / `SIGKILL`.

---

## 3. Hardware Compute Acceleration by Platform

```
+--------------------------------------------------------------------------+
|                        Berry AI Studio Core                              |
+--------------------------------------------------------------------------+
       |                                |                             |
       v                                v                             v
  Windows 10/11                       macOS                         Linux
  -------------                       -----                         -----
  * NVIDIA CUDA (Native)        * Apple Silicon Metal        * NVIDIA CUDA (Native)
  * AMD Radeon (DirectML)         (MPS Accelerate)           * AMD Radeon (ROCm 6.x)
  * Intel Arc (DirectML)                                     * Intel Arc (OneAPI IPEX)
```

---

## 4. Running from Source or Binary

### Windows
```powershell
# Launch workspace
.\berry.exe

# Headless generation
.\berry.exe run txt2img --prompt "Cinematic desert landscape" --output ./desert.png
```

### macOS & Linux
```bash
# Make binary executable
chmod +x ./berry

# Launch workspace
./berry

# Headless generation
./berry run txt2img --prompt "Cinematic desert landscape" --output ./desert.png
```

---

## 5. Verification Boundaries & Real Evidence Status

- **Windows 11 (x86_64, NVIDIA CUDA)**: **Verified**. Physical runs conducted for Rust launcher build, single-instance mutex, hermetic engine supervision, browser workspace launch, and SD 1.5 local generation via ComfyUI with NVIDIA RTX 3060 12GB.
- **macOS (Apple Silicon, Metal MPS)**: **Source Compatible**. Directory paths, browser launcher commands, Unix domain socket single-instance checks, and Metal fp16 flags implemented and unit-tested; native macOS binary bundling and physical Apple Silicon execution remain unverified in this session.
- **Linux (x86_64, ROCm / CUDA / OneAPI)**: **Source Compatible**. Supervisor process handling, Unix domain socket locking, and headless CLI generation implemented and unit-tested; native Linux binary packaging and physical AMD/Intel hardware execution remain unverified in this session.

