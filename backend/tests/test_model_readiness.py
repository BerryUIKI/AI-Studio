"""Container validation cannot imply engine-tested readiness."""

import json
from pathlib import Path
import struct

import pytest

from app.core.model_validation import inspect_model


def write_model(path: Path, header: dict, data: bytes = b"\0\0") -> Path:
    encoded = json.dumps(header).encode()
    path.write_bytes(struct.pack("<Q", len(encoded)) + encoded + data)
    return path


def tensor(shape: list[int] | None = None, offsets: list[int] | None = None) -> dict:
    return {"dtype": "F16", "shape": [1] if shape is None else shape, "data_offsets": [0, 2] if offsets is None else offsets}


def test_valid_scalar_empty_and_normal_tensors(tmp_path: Path) -> None:
    path = tmp_path / "model.safetensors"
    for shape, data in [([1], b"\0\0"), ([], b"\0\0"), ([0], b"")]:
        write_model(path, {"weight": tensor(shape, [0, len(data)])}, data)
        assert inspect_model(path).integrity == "structurally-valid"


@pytest.mark.parametrize("header,data", [
    ({"weight": tensor([2])}, b"\0\0"),
    ({"weight": tensor(offsets=[0, 4])}, b"\0\0"),
    ({"weight": tensor(offsets=[2, 4])}, b"\0" * 4),
    ({"weight": tensor(), "overlap": tensor()}, b"\0\0"),
    ({"weight": tensor()}, b"\0" * 4),
    ({"weight": tensor([-1])}, b"\0\0"),
    ({"weight": tensor([True])}, b"\0\0"),
    ({"__metadata__": {"architecture": 3}, "weight": tensor()}, b"\0\0"),
])
def test_invalid_tensor_layouts(tmp_path: Path, header: dict, data: bytes) -> None:
    assert inspect_model(write_model(tmp_path / "model.safetensors", header, data)).integrity == "invalid"


def test_duplicate_header_keys_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.safetensors"
    header = b'{"__metadata__":{},"__metadata__":{}}'
    path.write_bytes(struct.pack("<Q", len(header)) + header)
    assert inspect_model(path).integrity == "invalid"


def test_unknown_dtype_and_gguf_magic_are_unverified(tmp_path: Path) -> None:
    descriptor = {**tensor(), "dtype": "FUTURE_SUBBYTE"}
    assert inspect_model(write_model(tmp_path / "future.safetensors", {"weight": descriptor})).integrity == "unverified"
    gguf = tmp_path / "unknown.gguf"
    gguf.write_bytes(b"not-a-real-model")
    assert inspect_model(gguf).integrity == "invalid"
    gguf.write_bytes(b"GGUF" + struct.pack("<I", 3))
    assert inspect_model(gguf).integrity == "unverified"
