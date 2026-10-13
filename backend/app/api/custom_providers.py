"""Thin transports for custom platform descriptors; no inference during setup."""

from fastapi import APIRouter, HTTPException

from app.core.workers import run_blocking
from app.runtime.credentials import credentials_manager
from app.runtime.custom_providers import CustomProviderRegistry
from app.schemas.custom_provider import CustomProviderRecord, SaveCustomProviderRequest

router = APIRouter(prefix="/api/v1/custom-providers", tags=["Custom platforms"])


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
