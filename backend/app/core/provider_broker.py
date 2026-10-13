"""JSON request mappings and credential-owned, same-origin provider HTTP."""

import json
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from app.runners.adapter_executor import AdapterError, AdapterOutput
from app.schemas.custom_provider import CustomProviderSpec

MAX_HTTP_BYTES = 16 * 1024 * 1024


def render_template(value: Any, inputs: dict[str, Any], depth: int = 0) -> Any:
    """Substitute declared values without evaluating Python or JavaScript."""
    if depth > 32:
        raise AdapterError("REST template exceeds the nesting limit")
    if isinstance(value, dict):
        return {
            key: render_template(item, inputs, depth + 1) for key, item in value.items()
        }
    if isinstance(value, list):
        return [render_template(item, inputs, depth + 1) for item in value]
    if not isinstance(value, str):
        return value
    pattern = r"\{\{([A-Za-z0-9_]+)\}\}"
    matches = re.findall(pattern, value)
    if any(
        name not in inputs
        or name.lower() in {"api_key", "sdk_key", "authorization", "token"}
        for name in matches
    ):
        raise AdapterError(
            "REST template references a missing or forbidden input; use protected credential settings"
        )
    complete = re.fullmatch(pattern, value)
    if complete:
        return inputs[complete.group(1)]
    return re.sub(pattern, lambda match: str(inputs[match.group(1)]), value)


def mapped_image_output(spec: CustomProviderSpec, response: Any) -> AdapterOutput:
    try:
        value = response
        for field in spec.result_path.split("."):
            value = value[int(field)] if isinstance(value, list) else value[field]
        if not isinstance(value, str) or not value:
            raise ValueError("Invalid mapped value")
    except (KeyError, IndexError, TypeError, ValueError):
        raise AdapterError(
            "Provider response does not match the configured image result path"
        ) from None
    return AdapterOutput(
        type="image",
        value={"url" if spec.response_format == "url" else "b64_json": value},
    )


def _redact(value: Any, key: str) -> Any:
    if not key:
        return value
    if isinstance(value, str):
        return value.replace(key, "[redacted]")
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    if isinstance(value, dict):
        return {_redact(name, key): _redact(item, key) for name, item in value.items()}
    return value


class ProviderBroker:
    def __init__(
        self,
        spec: CustomProviderSpec,
        key: str = "",
        fixture: Any = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.spec, self.key, self.fixture, self.client = spec, key, fixture, client
        self.request_count = 0
        self.dispatched = False

    async def request(self, operation: dict[str, Any]) -> Any:
        if set(operation) - {"method", "path", "body", "params"}:
            raise AdapterError(
                "Broker accepts only method, path, body and params; credentials remain host-owned"
            )
        method = operation.get("method", "POST")
        path = operation.get("path", "")
        if (
            method not in {"GET", "POST"}
            or not isinstance(path, str)
            or len(path) > 2048
        ):
            raise AdapterError("Unsupported broker method or path")
        parsed = urlsplit(path)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or "\\" in path
        ):
            raise AdapterError(
                "Broker path must stay on the configured platform; use params for queries"
            )
        endpoint = self.spec.endpoint
        url = urljoin(endpoint.rstrip("/") + "/", path) if path else endpoint
        origin = urlsplit(endpoint)
        target = urlsplit(url)
        if (target.scheme, target.netloc) != (origin.scheme, origin.netloc):
            raise AdapterError("Broker request cannot change platform origin")
        try:
            serialized = json.dumps(operation, allow_nan=False)
        except (ValueError, TypeError):
            raise AdapterError("Broker request must be JSON") from None
        if len(serialized.encode()) > MAX_HTTP_BYTES:
            raise AdapterError("Broker request exceeds the byte limit")
        if self.key and self.key in serialized:
            raise AdapterError(
                "Broker input contains a credential; use the configured authentication mode"
            )
        self.request_count += 1
        if self.request_count > self.spec.max_requests:
            raise AdapterError("Provider broker request limit exceeded")
        if self.fixture is not None:
            return _redact(self.fixture, self.key)
        if self.spec.auth != "none" and not self.key:
            raise AdapterError("Custom platform API key is missing")
        headers = {}
        if self.spec.auth == "bearer":
            headers["Authorization"] = f"Bearer {self.key}"
        elif self.spec.auth == "header":
            headers[self.spec.auth_header] = self.key
        if self.client is None:
            async with httpx.AsyncClient(
                timeout=self.spec.request_timeout, follow_redirects=False
            ) as client:
                return await self._send(client, method, url, headers, operation)
        return await self._send(self.client, method, url, headers, operation)

    async def _send(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: dict[str, str],
        operation: dict[str, Any],
    ) -> Any:
        self.dispatched = True
        try:
            async with client.stream(
                method,
                url,
                headers=headers,
                json=operation.get("body"),
                params=operation.get("params"),
                follow_redirects=False,
            ) as response:
                if response.status_code != 200:
                    raise AdapterError(
                        f"Custom platform request failed (HTTP {response.status_code}); no automatic retry was sent"
                    )
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > MAX_HTTP_BYTES:
                        raise AdapterError(
                            "Provider JSON response exceeds the byte limit"
                        )
                    data.extend(chunk)
            return _redact(json.loads(data), self.key)
        except httpx.RequestError:
            raise AdapterError(
                "Provider connection interrupted; remote outcome may be unknown. No automatic retry was sent."
            ) from None
        except ValueError:
            raise AdapterError("Provider returned an invalid JSON response") from None
