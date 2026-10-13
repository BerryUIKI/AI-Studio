"""Shared REST/script execution with revision approval and host-owned credentials."""

from typing import Any

from app.core.provider_broker import (
    ProviderBroker,
    mapped_image_output,
    render_template,
)
from app.core.workers import run_blocking
from app.runners.adapter_executor import AdapterError, AdapterOutput, execute_adapter
from app.runtime.credentials import CredentialManager
from app.runtime.custom_providers import CustomProviderRegistry
from app.runtime.sdk_environment import (
    prepare_sdk_environment,
    sdk_module_paths,
    sdk_ready,
)
from app.schemas.custom_provider import CustomProviderRecord


class CustomProviderService:
    def __init__(self, credentials: CredentialManager) -> None:
        self.credentials = credentials
        self.registry = CustomProviderRegistry(credentials.data_dir)

    async def record(self, identifier: str) -> CustomProviderRecord:
        return await run_blocking(self.registry.get, identifier)

    async def execute(
        self, identifier: str, inputs: dict[str, Any], fixture: Any = None
    ) -> tuple[AdapterOutput, int]:
        record = await self.record(identifier)
        spec = record.spec
        if (
            inputs.get("model") not in spec.models
            or inputs.get("action", "txt2img") not in spec.actions
        ):
            raise AdapterError(
                "Custom platform does not support the selected model or action"
            )
        if spec.mode != "rest" and not record.execution_trusted:
            raise AdapterError(
                "Review and explicitly approve this calling-code revision before execution"
            )
        key = self.credentials.get_key(spec.id) or ""
        broker = ProviderBroker(spec, key, fixture=fixture)
        if spec.mode == "rest":
            body = render_template(spec.body_template, inputs)
            response = await broker.request({"body": body})
            result = mapped_image_output(spec, response)
            result.applied_parameters = {"request_body": body}
        else:
            if not spec.source.strip():
                raise AdapterError("Calling code is missing")
            module_paths = None
            sdk_key = None
            if spec.mode == "python_sdk":
                if not await run_blocking(sdk_ready, spec, self.credentials.data_dir):
                    raise AdapterError(
                        "Prepare the approved SDK environment before execution"
                    )
                module_paths = await run_blocking(
                    sdk_module_paths, spec, self.credentials.data_dir
                )
                if fixture is None and spec.sdk_allow_credentials:
                    sdk_key = key
            result = await execute_adapter(
                language=spec.mode,
                source=spec.source,
                inputs={**inputs, "endpoint": spec.endpoint},
                broker=broker.request,
                timeout=spec.worker_timeout,
                max_requests=spec.max_requests,
                module_paths=module_paths,
                sdk_key=sdk_key,
            )
        return result, broker.request_count

    async def prepare_sdk(self, identifier: str) -> None:
        await prepare_sdk_environment(
            await self.record(identifier), self.credentials.data_dir
        )
