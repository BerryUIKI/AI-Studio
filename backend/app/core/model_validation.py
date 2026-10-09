"""Inspect model containers without deserializing executable weights or importing torch.

Safetensors layout: https://github.com/safetensors/safetensors#format
Structural validity does not establish model completeness or engine compatibility.
"""

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import struct
from typing import Any, Literal

IntegrityStatus = Literal["structurally-valid", "invalid", "unverified"]
_DTYPE_BYTES = {
    "BOOL": 1, "U8": 1, "I8": 1, "F8_E4M3": 1, "F8_E5M2": 1,
    "I16": 2, "U16": 2, "F16": 2, "BF16": 2,
    "I32": 4, "U32": 4, "F32": 4, "I64": 8, "U64": 8, "F64": 8,
}


@dataclass
class ModelInspection:
    integrity: IntegrityStatus
    format_recognized: bool = False
    header: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    reason: str | None = None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate header key")
        result[key] = value
    return result


def inspect_model(path: Path) -> ModelInspection:
    if path.suffix.lower() != ".safetensors":
        if path.suffix.lower() == ".gguf":
            with path.open("rb") as source:
                prefix = source.read(8)
            if len(prefix) < 8 or prefix[:4] != b"GGUF":
                return ModelInspection("invalid", reason="Missing GGUF signature/version")
            return ModelInspection("unverified", True, reason="GGUF payload and architecture have not been validated")
        return ModelInspection("unverified", reason="This container is not safely validated by the catalog")
    try:
        size = path.stat().st_size
        with path.open("rb") as source:
            prefix = source.read(8)
            if len(prefix) != 8:
                raise ValueError("Truncated safetensors header length")
            length = struct.unpack("<Q", prefix)[0]
            if not 0 < length <= min(100 * 1024 * 1024, size - 8):
                raise ValueError("Invalid safetensors header length")
            raw = source.read(length)
        if not raw.startswith(b"{"):
            raise ValueError("Safetensors header must start with an object")
        header = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(header, dict):
            raise ValueError("Invalid tensor header")
        metadata = header.get("__metadata__", {})
        if not isinstance(metadata, dict) or any(not isinstance(v, str) for v in metadata.values()):
            raise ValueError("Metadata must map strings to strings")
        ranges: list[tuple[int, int]] = []
        unknown_dtype = False
        for name, tensor in header.items():
            if name == "__metadata__":
                continue
            if not isinstance(tensor, dict):
                raise ValueError("Invalid tensor descriptor")
            shape, offsets, dtype = tensor.get("shape"), tensor.get("data_offsets"), tensor.get("dtype")
            if not isinstance(shape, list) or any(type(n) is not int or n < 0 for n in shape):
                raise ValueError("Invalid tensor shape")
            if not isinstance(offsets, list) or len(offsets) != 2 or any(type(n) is not int for n in offsets):
                raise ValueError("Invalid tensor offsets")
            start, end = offsets
            if not 0 <= start <= end <= size - 8 - length:
                raise ValueError("Tensor data extends outside the file")
            if not isinstance(dtype, str):
                raise ValueError("Invalid tensor dtype")
            width = _DTYPE_BYTES.get(dtype)
            if width is None:
                unknown_dtype = True
            elif math.prod(shape) * width != end - start:
                raise ValueError("Tensor byte count does not match its shape/dtype")
            ranges.append((start, end))
        cursor = 0
        for start, end in sorted(ranges):
            if start != cursor:
                raise ValueError("Tensor data contains gaps or overlapping ranges")
            cursor = end
        if cursor != size - 8 - length:
            raise ValueError("Unindexed trailing tensor data")
        if unknown_dtype:
            return ModelInspection("unverified", True, header, metadata, "Unsupported tensor dtype")
        return ModelInspection("structurally-valid", True, header, metadata)
    except (ValueError, OSError, UnicodeError, struct.error) as error:
        return ModelInspection("invalid", reason=str(error))
