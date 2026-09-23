"""
Model Catalog and High-Performance File Scanner.

Discovers safetensors, ckpt, pth, and gguf models in registered root directories.
Parses .safetensors header metadata using standard library binary structs without
importing PyTorch or loading weight tensors into memory.
"""

import asyncio
import hashlib
import json
import logging
import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.runtime.supervisor import get_default_engine_dir
from app.schemas.model import (
    ModelArchitecture,
    ModelCategory,
    ModelRecord,
    ModelRoot,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".safetensors", ".ckpt", ".pth", ".pt", ".bin", ".gguf"}


def parse_safetensors_header(file_path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Read only the header of a .safetensors file without loading tensor data.
    Safetensors format:
      [0..7]: 8-byte uint64 little-endian representing header size N
      [8..8+N]: UTF-8 JSON header containing metadata and tensor specs
    """
    try:
        with open(file_path, "rb") as f:
            length_bytes = f.read(8)
            if len(length_bytes) < 8:
                return {}, {}
            header_len = struct.unpack("<Q", length_bytes)[0]
            if header_len <= 0 or header_len > 100 * 1024 * 1024:  # sanity limit 100MB
                return {}, {}
            header_bytes = f.read(header_len)
            header_json = json.loads(header_bytes.decode("utf-8", errors="replace"))

            metadata = header_json.get("__metadata__", {})
            return header_json, metadata
    except Exception as e:
        logger.debug(f"Failed to parse safetensors header for {file_path}: {e}")
        return {}, {}


def detect_architecture(
    file_path: Path, header: Dict[str, Any], metadata: Dict[str, Any]
) -> ModelArchitecture:
    """Infer model architecture from safetensors metadata, tensor keys, or filename."""
    # 1. Check explicit metadata
    arch_meta = metadata.get("modelspec.architecture", "").lower()
    if "flux" in arch_meta:
        return ModelArchitecture.FLUX
    if "xl" in arch_meta or "sdxl" in arch_meta:
        return ModelArchitecture.SDXL
    if "sd-1" in arch_meta or "sd1" in arch_meta:
        return ModelArchitecture.SD15
    if "sd3" in arch_meta:
        return ModelArchitecture.SD3

    # 2. Check tensor key patterns
    keys = list(header.keys())
    if any("double_blocks" in k for k in keys):
        return ModelArchitecture.FLUX
    if any("joint_blocks" in k for k in keys):
        return ModelArchitecture.SD3

    # Check cross-attention projection dimension in UNet
    # SDXL: 2048, SD 1.5: 768, SD 2.1: 1024
    for k, v in header.items():
        if isinstance(v, dict) and "shape" in v:
            shape = v.get("shape", [])
            if "attn2.to_k.weight" in k:
                if len(shape) >= 2 and shape[1] == 2048:
                    return ModelArchitecture.SDXL
                elif len(shape) >= 2 and shape[1] == 768:
                    return ModelArchitecture.SD15
                elif len(shape) >= 2 and shape[1] == 1024:
                    return ModelArchitecture.SD21

    # 3. Fallback to path / filename keywords
    name_lower = file_path.name.lower()
    if "flux" in name_lower:
        return ModelArchitecture.FLUX
    if "xl" in name_lower or "sdxl" in name_lower:
        return ModelArchitecture.SDXL
    if "v1-5" in name_lower or "sd15" in name_lower or "sd1.5" in name_lower or "1.5" in name_lower:
        return ModelArchitecture.SD15
    if "esrgan" in name_lower or "ultrasharp" in name_lower:
        return ModelArchitecture.ESRGAN

    return ModelArchitecture.UNKNOWN


def detect_category(file_path: Path, header: Dict[str, Any]) -> ModelCategory:
    """Classify model into Checkpoint, LoRA, VAE, ControlNet, or Upscaler."""
    path_str = str(file_path).lower()
    if "loras" in path_str or "lora" in path_str:
        return ModelCategory.LORA
    if "vae" in path_str:
        return ModelCategory.VAE
    if "controlnet" in path_str:
        return ModelCategory.CONTROLNET
    if "upscale" in path_str:
        return ModelCategory.UPSCALER
    if "checkpoints" in path_str:
        return ModelCategory.CHECKPOINT

    # Inspect tensor structure
    keys = list(header.keys())
    if any(k.startswith("lora_") or "lora_up" in k or "lora_down" in k for k in keys):
        return ModelCategory.LORA
    if all(k.startswith("first_stage_model.") or k.startswith("encoder.") or k.startswith("decoder.") for k in keys if k != "__metadata__"):
        return ModelCategory.VAE
    if any("diffusion_model" in k for k in keys):
        return ModelCategory.CHECKPOINT

    return ModelCategory.UNKNOWN


class ModelStore:
    """Manages model roots, directory scans, and model inventory."""

    def __init__(self, engine_dir: Optional[Path] = None) -> None:
        self.engine_dir = engine_dir or get_default_engine_dir()
        self.roots: Dict[str, ModelRoot] = {}
        self._cached_records: Dict[str, Tuple[float, int, ModelRecord]] = {}  # path -> (mtime, size, record)
        self._init_default_roots()

    def _init_default_roots(self) -> None:
        """Register default model directories for ComfyUI and WebUI."""
        default_models = self.engine_dir / "models"
        comfy_models = self.engine_dir / "comfyui" / "models"
        webui_models = self.engine_dir / "webui" / "models"

        self.add_root("default_engine", str(default_models), "Berry Engine Models", engine_type="comfyui")
        if comfy_models.exists():
            self.add_root("comfy_internal", str(comfy_models), "ComfyUI Models", engine_type="comfyui")
        if webui_models.exists():
            self.add_root("webui_internal", str(webui_models), "SD WebUI Models", engine_type="webui")

    def add_root(self, root_id: str, path_str: str, label: str, engine_type: Optional[str] = None) -> ModelRoot:
        """Register a directory to scan for models."""
        p = Path(path_str).resolve()
        root = ModelRoot(
            id=root_id,
            path=str(p),
            label=label,
            engine_type=engine_type,
            exists=p.is_dir(),
        )
        self.roots[root_id] = root
        return root

    def list_roots(self) -> List[ModelRoot]:
        """Return all registered model scan roots with updated existence checks."""
        for root in self.roots.values():
            root.exists = Path(root.path).is_dir()
        return list(self.roots.values())

    def _scan_file(self, file_path: Path) -> Optional[ModelRecord]:
        """Scan a single model file using header inspection."""
        try:
            stat = file_path.stat()
            mtime = stat.st_mtime
            size_bytes = stat.st_size
            path_str = str(file_path)

            # Check cache
            if path_str in self._cached_records:
                cached_mtime, cached_size, record = self._cached_records[path_str]
                if cached_mtime == mtime and cached_size == size_bytes:
                    return record

            ext = file_path.suffix.lower()
            header: Dict[str, Any] = {}
            metadata: Dict[str, Any] = {}

            if ext == ".safetensors":
                header, metadata = parse_safetensors_header(file_path)

            category = detect_category(file_path, header)
            architecture = detect_architecture(file_path, header, metadata)

            # Engine compatibility
            engine_compat = ["comfyui"]
            if ext in {".safetensors", ".ckpt"}:
                engine_compat.append("webui")

            # Missing dependencies / guidance
            dependencies: List[str] = []
            guidance: Optional[str] = None

            if architecture == ModelArchitecture.FLUX:
                dependencies = ["clip_l", "t5xxl", "ae (vae)"]
                guidance = "Flux Schnell/Dev requires separate CLIP/T5 text encoders and VAE if unbundled."
            elif architecture == ModelArchitecture.SDXL:
                guidance = "SDXL model operates best with 1024x1024 resolution."

            record_id = hashlib.sha256(f"{path_str}:{size_bytes}".encode("utf-8")).hexdigest()[:16]
            size_mb = round(size_bytes / (1024 * 1024), 2)

            record = ModelRecord(
                id=record_id,
                name=file_path.stem,
                file_path=path_str,
                category=category,
                architecture=architecture,
                format=ext.lstrip("."),
                size_bytes=size_bytes,
                size_mb=size_mb,
                engine_compatibility=engine_compat,
                is_ready=len(dependencies) == 0,
                missing_dependencies=dependencies,
                guidance=guidance,
                metadata={k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))},
            )

            self._cached_records[path_str] = (mtime, size_bytes, record)
            return record

        except Exception as e:
            logger.warning(f"Error scanning model file {file_path}: {e}")
            return None

    def scan_all_roots(self) -> List[ModelRecord]:
        """Scan all active root directories and return discovered models."""
        discovered: List[ModelRecord] = []
        for root in self.roots.values():
            root_path = Path(root.path)
            if not root_path.is_dir():
                root.exists = False
                root.models_found = 0
                continue

            root.exists = True
            count = 0
            for root_dir, _, files in os.walk(root_path):
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        f_path = Path(root_dir) / f
                        rec = self._scan_file(f_path)
                        if rec:
                            discovered.append(rec)
                            count += 1
            root.models_found = count

        return discovered

    async def scan_all_roots_async(self) -> List[ModelRecord]:
        """Asynchronously scan all model roots."""
        return await asyncio.to_thread(self.scan_all_roots)


# Global model store singleton
model_store = ModelStore()
