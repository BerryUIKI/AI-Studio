"""Contract failures must never submit inference or report successful graphs."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.cache import cache_store
from app.main import NODE_RUNNERS, app
from app.schemas.events import NodeStatusEvent


def graph() -> dict:
    return {
        "nodes": [
            {"id": "text", "type": "input.text", "params": {"value": "hello"}},
            {"id": "image", "type": "image.generate"},
        ],
        "edges": [{"id": "e", "source": "text", "source_handle": "text", "target": "image", "target_handle": "prompt"}],
    }


def events_for(payload: dict) -> list[dict]:
    events = []
    with TestClient(app).websocket_connect("/ws/workflow/run") as ws:
        ws.send_json({"graph": payload})
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["type"] in {"GRAPH_FINISHED", "ERROR"}:
                return events


@pytest.mark.parametrize("defect", ["runner", "required", "source_port", "target_port", "type", "multiple", "node_id", "edge_id", "dangling"])
def test_invalid_contract_prevents_inference(defect: str, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = graph()
    runner = AsyncMock()
    monkeypatch.setitem(NODE_RUNNERS, "image.generate", runner)
    if defect == "runner":
        monkeypatch.delitem(NODE_RUNNERS, "image.generate")
    elif defect == "required":
        payload["edges"] = []
    elif defect == "source_port":
        payload["edges"][0]["source_handle"] = "missing"
    elif defect == "target_port":
        payload["edges"][0]["target_handle"] = "missing"
    elif defect == "type":
        payload["edges"][0]["target_handle"] = "ref_image"
    elif defect == "multiple":
        payload["edges"].append({**payload["edges"][0], "id": "second"})
    elif defect == "node_id":
        payload["nodes"].append(payload["nodes"][0])
    elif defect == "edge_id":
        payload["edges"].append(payload["edges"][0])
    elif defect == "dangling":
        payload["edges"][0]["source"] = "missing"

    events = events_for(payload)
    assert not any(event["type"] == "NODE_OUTPUT" for event in events)
    assert events[-1].get("status") != "completed"
    runner.assert_not_called()
    response = TestClient(app).post("/api/v1/workflow/plan", json=payload)
    assert response.status_code in {400, 404}


def test_missing_runner_reports_failed_terminal_and_blocks_dependents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(NODE_RUNNERS, "input.text")
    events = events_for(graph())
    assert events[-1]["type"] == "GRAPH_FINISHED"
    assert events[-1]["status"] == "failed"
    assert any(event.get("node_id") == "image" and event.get("status") == "cancelled" for event in events)


def test_missing_declared_output_fails_and_never_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    async def empty_runner(node_id: str, params: dict):
        yield NodeStatusEvent(node_id=node_id, status="completed")

    monkeypatch.setattr("app.main.run_input_text_node", empty_runner)
    cache_store.clear()
    events = events_for({"nodes": [{"id": "text", "type": "input.text", "params": {"value": "missing output regression"}}]})
    assert events[-1]["status"] == "failed"
    assert any(event["type"] == "NODE_ERROR" for event in events)
