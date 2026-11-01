"""Thin transports for custom platform descriptors; no inference during setup."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, JsonValue

from app.core.custom_provider_service import CustomProviderService
from app.core.workers import run_blocking
from app.runners.adapter_executor import AdapterError, AdapterOutput
from app.runtime.credentials import credentials_manager
from app.runtime.custom_providers import CustomProviderRegistry
from app.schemas.custom_provider import CustomProviderRecord, SaveCustomProviderRequest

router = APIRouter(prefix="/api/v1/custom-providers", tags=["Custom platforms"])


class FixtureRequest(BaseModel):
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    response: JsonValue = Field(
        default_factory=lambda: {"data": [{"url": "https://fixture.invalid/image.jpg"}]}
    )


class FixtureResult(BaseModel):
    output: AdapterOutput
    broker_requests: int
    evidence_level: str = "broker-fixture"
    live_inference: bool = False


def provider_registry() -> CustomProviderRegistry:
    return CustomProviderRegistry(credentials_manager.data_dir)


@router.get("")
async def list_custom_providers() -> list[CustomProviderRecord]:
    return await run_blocking(provider_registry().list)


@router.put("")
async def save_custom_provider(
    request: SaveCustomProviderRequest,
) -> CustomProviderRecord:
    try:
        return await run_blocking(
            provider_registry().save, request.spec, request.approve_execution
        )
    except (ValueError, OSError):
        raise HTTPException(400, "Custom platform could not be saved") from None


@router.delete("/{identifier}")
async def delete_custom_provider(identifier: str) -> dict[str, bool]:
    try:
        registry = provider_registry()
        await run_blocking(registry.get, identifier)
        await run_blocking(credentials_manager.delete_key, identifier)
        await run_blocking(registry.delete, identifier)
    except LookupError:
        raise HTTPException(404, "Custom platform not found") from None
    except (ValueError, OSError):
        raise HTTPException(400, "Custom platform could not be removed") from None
    return {"success": True}


@router.post("/{identifier}/fixture", response_model=FixtureResult)
async def test_custom_provider_fixture(
    identifier: str, request: FixtureRequest
) -> FixtureResult:
    service = CustomProviderService(credentials_manager)
    try:
        record = await service.record(identifier)
        inputs = {
            "model": record.spec.models[0],
            "action": record.spec.actions[0],
            "prompt": "Fixture prompt",
            "width": 1024,
            "height": 1024,
            "input_image": "",
            "mask_image": "",
            **request.inputs,
        }
        if request.response is None:
            raise AdapterError("A broker fixture response is required")
        output, requests = await service.execute(
            identifier, inputs, fixture=request.response
        )
        return FixtureResult(output=output, broker_requests=requests)
    except LookupError:
        raise HTTPException(404, "Custom platform not found") from None
    except (AdapterError, ValueError):
        raise HTTPException(
            400,
            "Calling-code fixture failed. Verify output mapping, code, trust, SDK environment and request limits. No broker HTTP was sent.",
        ) from None


@router.post("/{identifier}/prepare-sdk")
async def prepare_custom_provider_sdk(identifier: str) -> dict[str, bool]:
    try:
        await CustomProviderService(credentials_manager).prepare_sdk(identifier)
    except LookupError:
        raise HTTPException(404, "Custom platform not found") from None
    except AdapterError as error:
        raise HTTPException(400, str(error)) from None
    return {"ready": True}
