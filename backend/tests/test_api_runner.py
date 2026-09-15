"""Tests for API runner dispatch, passthrough, and WebSocket execution endpoint."""

import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.cache import cache_store
from app.runners.api_runner import run_input_text_node

client = TestClient(app)


# ---------------------------------------------------------------------------
# input.text passthrough
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_input_text_passthrough():
    events = []
    async for event in run_input_text_node("n1", {"value": "hello world"}):
        events.append(event)

    types = [e.type for e in events]
    assert "NODE_STATUS" in types
    assert "NODE_OUTPUT" in types

    output_event = next(e for e in events if e.type == "NODE_OUTPUT")
    assert output_event.output == {"text": "hello world"}


# ---------------------------------------------------------------------------
# WebSocket workflow execution (passthrough only, no real API calls)
# ---------------------------------------------------------------------------

def test_websocket_run_single_input_node():
    """Running a single input.text node over WebSocket should stream events and finish."""
    cache_store.clear()

    graph = {
        "nodes": [{"id": "n1", "type": "input.text", "params": {"value": "test prompt"}}],
        "edges": [],
    }

    with client.websocket_connect("/ws/workflow/run") as ws:
        ws.send_text(json.dumps(graph))
        events = []
        while True:
            raw = ws.receive_text()
            data = json.loads(raw)
            events.append(data)
            if data["type"] == "GRAPH_FINISHED":
                break

    event_types = [e["type"] for e in events]
    assert "GRAPH_STARTED" in event_types
    assert "NODE_STATUS" in event_types
    assert "NODE_OUTPUT" in event_types
    assert "GRAPH_FINISHED" in event_types

    # Result text should match input
    output_event = next(e for e in events if e["type"] == "NODE_OUTPUT")
    assert output_event["output"]["text"] == "test prompt"


def test_websocket_run_uses_cache_on_second_call():
    """Second run of same graph should hit cache for the input.text node."""
    cache_store.clear()

    graph = {
        "nodes": [{"id": "n1", "type": "input.text", "params": {"value": "cached value"}}],
        "edges": [],
    }

    # First run: populates cache
    with client.websocket_connect("/ws/workflow/run") as ws:
        ws.send_text(json.dumps(graph))
        while True:
            data = json.loads(ws.receive_text())
            if data["type"] == "GRAPH_FINISHED":
                break

    # Second run: should report NODE_STATUS=cached
    cached_events = []
    with client.websocket_connect("/ws/workflow/run") as ws:
        ws.send_text(json.dumps(graph))
        while True:
            data = json.loads(ws.receive_text())
            cached_events.append(data)
            if data["type"] == "GRAPH_FINISHED":
                break

    status_events = [e for e in cached_events if e["type"] == "NODE_STATUS"]
    assert any(e["status"] == "cached" for e in status_events)


def test_websocket_invalid_payload():
    """Sending malformed JSON should close the WebSocket gracefully."""
    with client.websocket_connect("/ws/workflow/run") as ws:
        ws.send_text("not valid json at all")
        response = json.loads(ws.receive_text())
        assert response["type"] == "ERROR"
