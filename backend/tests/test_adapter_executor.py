"""Real owned worker processes; broker fixtures send no network requests."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from app.runners.adapter_executor import AdapterError, execute_adapter

JS = """async function execute(input, ctx) {
  const response = await ctx.request({method: 'POST', body: {prompt: input.prompt}});
  return {type: 'image', value: {url: response.data[0].url}};
}"""
PY = """async def execute(input, ctx):
    response = await ctx.request({'method': 'POST', 'body': {'prompt': input['prompt']}})
    return {'type': 'image', 'value': {'url': response['data'][0]['url']}}
"""


@pytest.mark.asyncio
@pytest.mark.parametrize("language,source", [("javascript", JS), ("python", PY)])
async def test_dual_language_broker_normalization(language: str, source: str) -> None:
    broker = AsyncMock(
        return_value={"data": [{"url": "https://fixture.invalid/image.jpg"}]}
    )
    output = await execute_adapter(
        language=language, source=source, inputs={"prompt": "fixture"}, broker=broker
    )
    assert output.type == "image" and output.value == {
        "url": "https://fixture.invalid/image.jpg"
    }
    broker.assert_awaited_once_with({"method": "POST", "body": {"prompt": "fixture"}})


@pytest.mark.asyncio
async def test_javascript_has_no_node_or_network_globals() -> None:
    result = await execute_adapter(
        language="javascript",
        source="""function execute(input, ctx) {
      return {type:'json',value:[typeof process,typeof require,typeof fetch]};
    }""",
        inputs={},
        broker=AsyncMock(),
    )
    assert result.value == ["undefined", "undefined", "undefined"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language,source",
    [
        (
            "javascript",
            """async function execute(input, ctx) {
    await ctx.request({}); await ctx.request({}); return {type:'json',value:null}; }""",
        ),
        (
            "python",
            "async def execute(input,ctx):\n    await ctx.request({})\n    await ctx.request({})\n    return {'type':'json','value':None}",
        ),
    ],
)
async def test_broker_count_is_enforced_outside_code(
    language: str, source: str
) -> None:
    broker = AsyncMock(return_value={})
    with pytest.raises(AdapterError, match="request limit"):
        await execute_adapter(
            language=language, source=source, inputs={}, broker=broker, max_requests=1
        )
    assert broker.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language,source",
    [
        ("javascript", "function execute(){while(true){}}"),
        ("python", "def execute(input,ctx):\n    while True: pass"),
    ],
)
async def test_infinite_code_is_terminated(language: str, source: str) -> None:
    with pytest.raises(AdapterError):
        await asyncio.wait_for(
            execute_adapter(
                language=language,
                source=source,
                inputs={},
                broker=AsyncMock(),
                timeout=1,
            ),
            5,
        )


@pytest.mark.asyncio
async def test_sdk_credential_cannot_be_returned_or_logged_as_result() -> None:
    source = "def execute(input,ctx):\n    print(ctx.api_key)\n    return {'type':'string','value':ctx.api_key}"
    with pytest.raises(AdapterError, match="credential") as failure:
        await execute_adapter(
            language="python_sdk",
            source=source,
            inputs={},
            broker=AsyncMock(),
            sdk_key="fixture-private-secret",
        )
    assert "fixture-private-secret" not in str(failure.value)


@pytest.mark.asyncio
async def test_unknown_port_type_is_rejected() -> None:
    with pytest.raises(AdapterError, match="five-type"):
        await execute_adapter(
            language="javascript",
            source="function execute(){return {type:'tensor',value:1}}",
            inputs={},
            broker=AsyncMock(),
        )


@pytest.mark.asyncio
async def test_unicode_escaped_credential_is_still_rejected() -> None:
    source = "def execute(input,ctx):\n    return {'type':'json','value':{'secret':ctx.api_key}}"
    with pytest.raises(AdapterError, match="credential"):
        await execute_adapter(
            language="python_sdk",
            source=source,
            inputs={},
            broker=AsyncMock(),
            sdk_key='fixture-密钥"quote',
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("port", ["string", "image", "audio", "video", "json"])
async def test_all_five_output_ports_remain_supported(port: str) -> None:
    source = "function execute(input){return {type:input.port,value:input.value}}"
    result = await execute_adapter(
        language="javascript",
        source=source,
        inputs={"port": port, "value": "fixture"},
        broker=AsyncMock(),
    )
    assert result.type == port and result.value == "fixture"
