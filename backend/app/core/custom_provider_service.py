"""Shared REST/script execution with revision approval and host-owned credentials."""

import asyncio
import sys
from importlib.metadata import version
from typing import Any

from app.core.provider_broker import (
    ProviderBroker,
    mapped_image_output,
    render_template,
)
from app.core.workers import run_blocking
from app.runners.adapter_executor import (
    AdapterError,
    AdapterOutput,
    _contains_secret,
    execute_adapter,
)
from app.runtime.credentials import CredentialManager
from app.runtime.custom_providers import CustomProviderRegistry
from app.runtime.sdk_environment import (
    prepare_sdk_environment,
    sdk_dependency_revision,
    sdk_module_paths,
    sdk_ready,
)
from app.schemas.custom_provider import CustomProviderRecord
from app.storage.task_store import record_remote_job


class AdapterCancelled(AdapterError):
    def __init__(self, outcome_unknown: bool) -> None:
        self.outcome_unknown = outcome_unknown
        super().__init__(
            "Local adapter stopped. Remote work may continue and incur charges; its outcome is unknown. No automatic retry was sent."
            if outcome_unknown
            else "Adapter cancelled before dispatch; no provider request was sent."
        )


class CustomProviderService:
    def __init__(self, credentials: CredentialManager) -> None:
        self.credentials = credentials
        self.registry = CustomProviderRegistry(credentials.data_dir)

    async def record(self, identifier: str) -> CustomProviderRecord:
        return await run_blocking(self.registry.get, identifier)

    def snapshot(
        self, identifier: str, inputs: dict[str, Any], *, require_key: bool = True
    ) -> tuple[CustomProviderRecord, dict[str, Any], str]:
        """Freeze the descriptor and credential used by one execution."""
        record = self.registry.get(identifier)
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
        key = self.credentials.get_key(identifier) or ""
        if require_key and spec.auth != "none" and not key:
            raise AdapterError("Custom platform API key is missing")
        identity = {
            "provider_revision": spec.revision,
            "credential_revision": self.credentials.key_revision(identifier),
            "endpoint": spec.endpoint,
            "mode": spec.mode,
            "runtime_revision": version("quickjs-ng")
            if spec.mode == "javascript"
            else sys.version,
            "dependency_revision": sdk_dependency_revision(
                spec, self.credentials.data_dir
            )
            if spec.mode == "python_sdk"
            else None,
        }
        return record, identity, key

    async def execute(
        self,
        identifier: str,
        inputs: dict[str, Any],
        fixture: Any = None,
        expected_identity: dict[str, Any] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> tuple[AdapterOutput, int]:
        record, identity, key = await run_blocking(
            self.snapshot, identifier, inputs, require_key=fixture is None
        )
        if expected_identity is not None and identity != expected_identity:
            raise AdapterError(
                "Platform configuration, credential or dependencies changed; refresh setup before creating again"
            )
        spec = record.spec
        if set(inputs) & {"api_key", "sdk_key", "authorization", "token"}:
            raise AdapterError(
                "Credentials must use protected platform settings, not calling-code inputs"
            )
        broker = ProviderBroker(spec, key, fixture=fixture)

        async def on_job(job_id: str) -> None:
            if key and _contains_secret(job_id, key):
                raise AdapterError("Provider job ID contains a credential")
            if fixture is None:
                await record_remote_job(job_id)

        async def invoke() -> AdapterOutput:
            if spec.mode == "rest":
                body = render_template(spec.body_template, inputs)
                response = await broker.request({"body": body})
                result = mapped_image_output(spec, response)
                result.applied_parameters = {"request_body": body}
                return result
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
            return await execute_adapter(
                language=spec.mode,
                source=spec.source,
                inputs={**inputs, "endpoint": spec.endpoint},
                broker=broker.request,
                timeout=spec.worker_timeout,
                max_requests=spec.max_requests,
                module_paths=module_paths,
                sdk_key=sdk_key,
                on_job=on_job,
            )

        if cancel_event is None:
            result = await invoke()
        else:
            if cancel_event.is_set():
                raise AdapterCancelled(False)
            work = asyncio.create_task(invoke())
            cancellation = asyncio.create_task(cancel_event.wait())
            try:
                await asyncio.wait(
                    {work, cancellation}, return_when=asyncio.FIRST_COMPLETED
                )
                if work.done():
                    result = await work
                else:
                    work.cancel()
                    await asyncio.gather(work, return_exceptions=True)
                    raise AdapterCancelled(broker.dispatched or spec.mode != "rest")
            finally:
                cancellation.cancel()
                if not work.done():
                    work.cancel()
                await asyncio.gather(work, cancellation, return_exceptions=True)
        # Script output and provenance must not echo even broker-owned credentials.
        if key and _contains_secret(result.model_dump(mode="json"), key):
            raise AdapterError("Calling-code output contains a credential")
        if expected_identity is not None:
            _, current, _ = await run_blocking(
                self.snapshot, identifier, inputs, require_key=fixture is None
            )
            if current != expected_identity:
                raise AdapterError(
                    "Platform changed during execution; remote outcome may have completed. No automatic retry was sent."
                )
        return result, broker.request_count

    async def prepare_sdk(self, identifier: str) -> None:
        await prepare_sdk_environment(
            await self.record(identifier), self.credentials.data_dir
        )
