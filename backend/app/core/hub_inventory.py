"""Resolve catalog installation evidence from the actual model inventory."""

from pathlib import Path
from urllib.parse import unquote, urlparse

from app.schemas.model import ModelRecord
from app.schemas.model_hub import HubModelRecord


def reconcile_hub_inventory(models: list[HubModelRecord], inventory: list[ModelRecord]) -> list[HubModelRecord]:
    result = []
    for model in models:
        filenames = {unquote(Path(urlparse(source.url).path).name) for source in model.sources}
        matches = [record for record in inventory if (
            record.content_hash == model.sha256 if model.sha256 else
            Path(record.file_path).name in filenames and record.size_bytes == model.size_bytes
        )]
        record = matches[0] if len(matches) == 1 else None
        result.append(model.model_copy(update={
            "is_installed": record is not None,
            "installed_path": record.file_path if record else None,
            "installed_model_id": record.id if record else None,
            "is_ready": bool(record and record.is_ready),
            "engine_compatibility": record.engine_compatibility if record else [],
            "guidance": record.guidance if record else "Install this model, then validate its engine readiness in Models.",
        }))
    return result
