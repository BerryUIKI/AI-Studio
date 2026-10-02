"""Unit tests for node schema validation, registry, and endpoints."""

from fastapi.testclient import TestClient
from app.main import app
from app.nodes.registry import registry
from app.schemas.node import DataType, NodeCategory

client = TestClient(app)


def test_registry_contains_builtin_nodes():
    nodes = registry.list_all()
    assert len(nodes) >= 4
    types = {n.type for n in nodes}
    assert "input.text" in types
    assert "text.llm" in types
    assert "image.generate" in types
    assert "output.preview" in types


def test_ports_strictly_follow_5_types():
    allowed_types = {t.value for t in DataType}
    for node in registry.list_all():
        for port in node.inputs + node.outputs:
            assert port.type.value in allowed_types


def test_get_nodes_endpoint():
    response = client.get("/api/v1/nodes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 4

    # Verify FLUX image gen node
    flux_node = next(item for item in data if item["type"] == "image.generate")
    assert flux_node["title"] == "Cloud Image Generator"
    assert flux_node["category"] == NodeCategory.IMAGE.value
    assert len(flux_node["inputs"]) == 2
    assert len(flux_node["outputs"]) == 1
