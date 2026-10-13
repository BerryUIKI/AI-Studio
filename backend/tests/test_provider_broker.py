"""Typed template substitution and no credential forwarding to other origins."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest
from app.core.provider_broker import (
    ProviderBroker,
    mapped_image_output,
    render_template,
)
from app.runners.adapter_executor import AdapterError
from app.schemas.custom_provider import CustomProviderSpec


def spec(**options: object) -> CustomProviderSpec:
    return CustomProviderSpec.model_validate(
        {
            "id": "custom-fixture",
            "name": "Fixture",
            "endpoint": "https://fixture.invalid/v1/images",
            "models": ["model"],
            "actions": ["txt2img"],
            **options,
        }
    )


def test_template_preserves_types_and_does_not_evaluate_code() -> None:
    template = {
        "size": "{{width}}x{{height}}",
        "count": "{{count}}",
        "nested": ["{{model}}"],
        "literal": "__import__('os')",
    }
    result = render_template(
        template, {"width": 1024, "height": 1024, "count": 1, "model": "fixture"}
    )
    assert result == {
        "size": "1024x1024",
        "count": 1,
        "nested": ["fixture"],
        "literal": "__import__('os')",
    }
    with pytest.raises(AdapterError):
        render_template("{{api_key}}", {"api_key": "fixture-secret"})


@pytest.mark.asyncio
async def test_same_origin_auth_mapping_redaction_and_no_redirect() -> None:
    calls: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["authorization"] == "Bearer fixture-secret"
        assert json.loads(request.content) == {"model": "model"}
        return httpx.Response(
            200,
            json={
                "data": [{"url": "https://media.invalid/output.jpg"}],
                "echo": "fixture-secret",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        broker = ProviderBroker(spec(), "fixture-secret", client=client)
        response = await broker.request({"body": {"model": "model"}})
    assert response["echo"] == "[redacted]" and len(calls) == 1
    assert mapped_image_output(spec(), response).value == {
        "url": "https://media.invalid/output.jpg"
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        {"path": "https://elsewhere.invalid"},
        {"path": "//elsewhere.invalid"},
        {"path": "?api_key=secret"},
        {"headers": {"Authorization": "fixture"}},
        {"method": "DELETE"},
    ],
)
async def test_invalid_broker_operations_never_send_http(
    operation: dict[str, object],
) -> None:
    client = AsyncMock()
    with pytest.raises(AdapterError):
        await ProviderBroker(spec(), "fixture", client=client).request(operation)
    client.stream.assert_not_called()


@pytest.mark.asyncio
async def test_http_redirect_cannot_forward_platform_key() -> None:
    calls: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(307, headers={"location": "https://elsewhere.invalid"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(transport), follow_redirects=True
    ) as client:
        with pytest.raises(AdapterError, match="307"):
            await ProviderBroker(spec(), "fixture", client=client).request({})
    assert len(calls) == 1
