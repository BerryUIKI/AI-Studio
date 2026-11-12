"""Container validation cannot imply engine-tested readiness."""

import json
from pathlib import Path
import struct

import pytest

from app.core.model_validation import inspect_model
from app.schemas.model import ModelArchitecture, ModelCategory
from app.storage.model_store import ModelStore


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


def test_unknown_models_not_ready_and_revision_uses_bytes(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    model = root / "unknown.gguf"
    model.write_bytes(b"not-a-real-model")
    store = ModelStore(tmp_path / "engine")
    store.add_root("fixture", str(root), "Fixture")
    record = store.scan_all_roots()[0]
    assert not record.is_ready
    assert record.integrity_status == "invalid"
    assert record.architecture == ModelArchitecture.UNKNOWN
    assert record.category == ModelCategory.UNKNOWN
    assert record.engine_compatibility == []
    assert record.possible_engines == []
    model.write_bytes(b"NOT-A-REAL-MODEL")
    changed = store.scan_all_roots()[0]
    assert changed.content_hash != record.content_hash
    assert changed.id != record.id


def component_header() -> dict:
    keys = ["text_model.embeddings.token_embedding.weight", "text_model.encoder.layers.11.weight",
            "encoder.block.23.layer.0.SelfAttention.q.weight", "shared.weight",
            "encoder.conv_in.weight", "decoder.conv_out.weight"]
    result = {}
    cursor = 0
    for key in keys:
        shape = [1, 768] if "token_embedding" in key else [1]
        length = 1536 if "token_embedding" in key else 2
        result[key] = tensor(shape, [cursor, cursor + length])
        cursor += length
    return result


def test_flux_dependencies_resolve_inventory_and_bundles(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    flux_header = {"double_blocks.0.weight": tensor()}
    flux_file = write_model(root / "flux.safetensors", flux_header)
    store = ModelStore(tmp_path / "engine")
    store.add_root("fixture", str(root), "Fixture")
    record = store.scan_all_roots()[0]
    assert record.missing_dependencies == ["clip_l", "t5xxl", "ae (vae)"]
    assert record.dependency_status == "missing"
    fake = root / "clip_l-t5xxl-ae.safetensors"
    fake.write_bytes(b"invalid")
    assert next(r for r in store.scan_all_roots() if r.name == "flux").dependency_status == "missing"
    components = component_header()
    component_file = write_model(root / "components.safetensors", components, b"\0" * 1546)
    record = next(r for r in store.scan_all_roots() if r.name == "flux")
    assert record.dependency_status == "present"
    assert record.missing_dependencies == []
    assert not record.is_ready
    component_file.unlink()
    assert next(r for r in store.scan_all_roots() if r.name == "flux").dependency_status == "missing"
    bundled = {**flux_header, **components}
    bundled["double_blocks.0.weight"] = tensor(offsets=[1546, 1548])
    write_model(flux_file, bundled, b"\0" * 1548)
    record = next(r for r in store.scan_all_roots() if r.name == "flux")
    assert record.dependency_status == "present"
    assert set(record.available_components) == {"clip_l", "t5xxl", "ae (vae)"}
