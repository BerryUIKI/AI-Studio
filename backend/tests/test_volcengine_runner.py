"""Ark payload, identity and failure contracts without paid inference."""

import base64
import json

import httpx
import pytest

from app.runners.volcengine_runner import ARK_IMAGE_ENDPOINT, SEEDREAM_MODEL, ArkError, request_ark_image


@pytest.mark.asyncio
async def test_exact_model_single_image_and_reference_payload() -> None:
    calls = []

    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert str(request.url) == ARK_IMAGE_ENDPOINT
        assert request.headers["authorization"] == "Bearer fixture-secret"
        payload = json.loads(request.content)
        assert payload == {"model": SEEDREAM_MODEL, "prompt": "fixture", "size": "1280x720",
            "sequential_image_generation": "disabled", "response_format": "url", "stream": False,
            "watermark": True, "image": "data:image/png;base64,ZmFrZQ=="}
        return httpx.Response(200, json={"model": "observed-model", "data": [{"url": "https://fixture.invalid/output.jpg"}]},
            headers={"x-request-id": "fixture-request"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        output = await request_ark_image(prompt="fixture", model=SEEDREAM_MODEL, width=1280, height=720,
            api_key="fixture-secret", image_data_uri="data:image/png;base64,ZmFrZQ==", client=client)
    assert len(calls) == 1
    assert output.requested_model == SEEDREAM_MODEL
    assert output.effective_model == "observed-model"
    assert output.request_id == "fixture-request"


@pytest.mark.asyncio
async def test_base64_response_keeps_content_and_unknown_model_identity() -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200,
        json={"data": [{"b64_json": base64.b64encode(b"fixture image bytes").decode()}]}))) as client:
        output = await request_ark_image(prompt="fixture", model=SEEDREAM_MODEL, width=1024, height=1024,
            api_key="fixture-secret", response_format="b64_json", client=client)
    assert output.content == b"fixture image bytes"
    assert output.url is None and output.effective_model is None


@pytest.mark.asyncio
@pytest.mark.parametrize("model,width,height,key", [("other-model", 1024, 1024, "key"),
    (SEEDREAM_MODEL, 512, 512, "key"), (SEEDREAM_MODEL, 1024, 1024, "")])
async def test_invalid_input_never_sends_inference(model: str, width: int, height: int, key: str) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid input sent a potentially paid request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as client:
        with pytest.raises(ArkError):
            await request_ark_image(prompt="fixture", model=model, width=width, height=height, api_key=key, client=client)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 404, 429, 500, 307])
async def test_errors_never_echo_credentials_retry_or_follow_redirects(status: int) -> None:
    calls = []

    def response(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "fixture-secret"}},
            headers={"location": "https://unrelated.invalid/steal"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(response), follow_redirects=True) as client:
        with pytest.raises(ArkError) as failure:
            await request_ark_image(prompt="fixture", model=SEEDREAM_MODEL, width=1024, height=1024,
                api_key="fixture-secret", client=client)
    assert "fixture-secret" not in str(failure.value)
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"data": []}, {"data": [{"url": "http://unsafe.invalid"}]},
    {"data": [{"url": "https://one.invalid"}, {"url": "https://two.invalid"}]}])
async def test_invalid_output_is_not_success(body: dict[str, object]) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as client:
        with pytest.raises(ArkError):
            await request_ark_image(prompt="fixture", model=SEEDREAM_MODEL, width=1024, height=1024,
                api_key="fixture-secret", client=client)


@pytest.mark.asyncio
@pytest.mark.parametrize("code,expected", [("ModelNotOpen", "ModelNotOpen"), ("fixture-secret", None),
    ("ark-fixture", None), ("<html>unsafe</html>", None)])
async def test_only_safe_error_codes_are_reported(code: str, expected: str | None) -> None:
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(404,
        json={"error": {"code": code, "message": "fixture-secret"}}))) as client:
        with pytest.raises(ArkError) as failure:
            await request_ark_image(prompt="fixture", model=SEEDREAM_MODEL, width=1024, height=1024,
                api_key="fixture-secret", client=client)
    assert "fixture-secret" not in str(failure.value)
    assert ("; code " in str(failure.value)) == (expected is not None)
    if expected:
        assert expected in str(failure.value)
