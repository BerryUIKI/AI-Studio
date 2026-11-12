"""Catalog installation is actual file evidence, not a download flag."""

from app.core.hub_inventory import reconcile_hub_inventory
from app.runtime.hardware_evaluator import evaluate_model_compatibility
from app.schemas.model import ModelRecord
from app.storage.hub_catalog import HubCatalog


def test_same_filename_with_wrong_content_does_not_claim_installation() -> None:
    model = HubCatalog.list_models()[0]
    record = ModelRecord(id='fixture', name='fixture', file_path=model.sources[0].url.split('/')[-1],
        category='checkpoint', architecture='flux', format='safetensors', size_bytes=model.size_bytes,
        size_mb=1, content_hash='wrong')
    assert not reconcile_hub_inventory([model], [record])[0].is_installed
    record.content_hash = model.sha256
    installed = reconcile_hub_inventory([model], [record])[0]
    assert installed.is_installed
    assert installed.installed_model_id == 'fixture'
    assert not installed.is_ready
    assert not model.is_installed


def test_capacity_estimate_uses_free_memory_and_discloses_assumptions() -> None:
    model = HubCatalog.list_models()[0]
    available = evaluate_model_compatibility(model, 24576, 20480, 32768, True)
    busy = evaluate_model_compatibility(model, 24576, 512, 32768, True)
    assert available.tier == 'optimal'
    assert busy.tier != 'optimal'
    assert busy.estimated_latency_sec.startswith('Estimate:')
    assert 'Unmeasured' in busy.notes
    assert str(model.recommended_resolution) in busy.notes
