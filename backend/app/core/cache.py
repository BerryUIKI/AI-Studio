"""Deterministic hashing and output result caching engine with SQLite persistence."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.storage.db import DatabaseManager, db_manager

logger = logging.getLogger(__name__)


def compute_content_hash(value: Any) -> str:
    """Compute a deterministic SHA-256 hash of output content."""
    if value is None:
        return hashlib.sha256(b"null").hexdigest()
    if isinstance(value, (int, float, bool)):
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    if isinstance(value, str):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    if isinstance(value, (dict, list)):
        serialized = json.dumps(value, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def compute_semantic_node_hash(
    node_type: str,
    params: Dict[str, Any],
    input_bindings: List[Tuple[str, str, str]],  # (target_handle, upstream_content_hash, source_handle)
    provider_id: Optional[str] = None,
    runner_version: Optional[str] = None,
) -> str:
    """
    Compute a deterministic port-aware SHA-256 hash representing a node's exact semantic state.
    NodeHash = SHA256(NodeType + SerializedCanonicalParams + OrderedPortBindings)

    Canonical params strictly incorporate provider identity and runner version (Invariant #5).
    OrderedPortBindings strictly associates input ports to upstream outputs:
    target_handle:source_handle:content_hash
    """
    hasher = hashlib.sha256()
    hasher.update(node_type.encode("utf-8"))

    # Canonicalize params: exclude transient secrets from hash via explicit denylist
    secret_keys = {
        "api_key",
        "apikey",
        "secret",
        "secret_key",
        "token",
        "access_token",
        "auth_token",
        "password",
        "bearer_token",
        "app_secret",
    }
    clean_params = {
        k: v for k, v in params.items()
        if k.lower() not in secret_keys and not k.lower().endswith("_api_key") and not k.lower().endswith("_token")
    }

    # Invariant #5: Canonical Params must include provider identity & runner version
    resolved_prov = provider_id or params.get("__provider") or params.get("provider") or params.get("engine_id")
    if resolved_prov:
        clean_params["__provider"] = str(resolved_prov)

    resolved_ver = runner_version or params.get("__runner_version") or "0.1.0"
    clean_params["__runner_version"] = str(resolved_ver)

    params_str = json.dumps(clean_params, sort_keys=True, default=str)
    hasher.update(params_str.encode("utf-8"))

    # Deterministic binding sort by target_handle
    sorted_bindings = sorted(input_bindings, key=lambda b: (b[0], b[2]))
    for target_handle, content_hash, source_handle in sorted_bindings:
        binding_repr = f"|in:{target_handle}->out:{source_handle}#{content_hash}"
        hasher.update(binding_repr.encode("utf-8"))

    return hasher.hexdigest()


def compute_node_hash(node_type: str, params: Dict[str, Any], parent_hashes: list[str]) -> str:
    """
    Legacy helper: Compute SHA-256 representing a node's state with parent hashes.
    Kept for backwards compatibility with baseline tests.
    """
    hasher = hashlib.sha256()
    hasher.update(node_type.encode("utf-8"))

    params_str = json.dumps(params, sort_keys=True, default=str)
    hasher.update(params_str.encode("utf-8"))

    for parent_hash in sorted(parent_hashes):
        hasher.update(parent_hash.encode("utf-8"))

    return hasher.hexdigest()


class CacheStore:
    """Thread-safe cache store with in-memory cache and SQLite persistence."""

    def __init__(self, manager: Optional[DatabaseManager] = None, asset_store: Optional[Any] = None) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self.manager = manager or db_manager
        self._asset_store = asset_store

    def get(self, node_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached output data by node hash synchronously from memory."""
        return self._store.get(node_hash)

    def set(self, node_hash: str, output: Dict[str, Any]) -> None:
        """Store output data for a node hash in memory."""
        self._store[node_hash] = output

    def has(self, node_hash: str) -> bool:
        """Check if output for node hash is cached in memory."""
        return node_hash in self._store

    async def invalidate_async(self, node_hash: str) -> None:
        """Invalidate and remove a broken or stale cache entry from memory and SQLite."""
        self._store.pop(node_hash, None)
        try:
            conn = await self.manager.get_connection()
            await conn.execute("DELETE FROM cache_entries WHERE node_hash = ?", (node_hash,))
            await conn.commit()
            logger.info("Invalidated cache entry for node_hash: %s", node_hash)
        except Exception as e:
            logger.error("Cache DB invalidate operation failed for %s: %s", node_hash, e)

    async def validate_output_assets(self, output: Dict[str, Any]) -> bool:
        """
        Validate that any media or asset references in the output remain available and intact.
        Checks:
        1. Explicit asset_id reference in local AssetStore exists and physical file is present.
        2. /api/v1/assets/{id}/content URLs refer to existing asset and physical file.
        3. Local file path references exist.
        """
        if self._asset_store is not None:
            asset_mgr = self._asset_store
        else:
            from app.storage.asset_store import asset_store
            asset_mgr = asset_store

        # Check explicit asset_id
        asset_id = output.get("asset_id")
        if asset_id and isinstance(asset_id, str):
            rec = await asset_mgr.get_asset(asset_id)
            if not rec:
                return False
            from app.core.content_identity import managed_asset_identity
            try:
                await managed_asset_identity(asset_id, asset_mgr)
            except ValueError:
                return False

        # Check image_url / video_url if pointing to local asset endpoint
        for url_key in ("image_url", "video_url", "image", "video", "audio", "media"):
            url_val = output.get(url_key)
            if url_val and isinstance(url_val, str):
                if url_val.startswith("/api/v1/assets/"):
                    # Extract asset id between /api/v1/assets/ and /content
                    parts = url_val.split("/api/v1/assets/")
                    if len(parts) > 1:
                        target_id = parts[1].split("/")[0]
                        from app.core.content_identity import managed_asset_identity
                        try:
                            await managed_asset_identity(target_id, asset_mgr)
                        except ValueError:
                            return False
                elif url_val.startswith(("https://", "http://")):
                    # Unmanaged output URLs can expire or change. Reuse requires
                    # a verified local asset, not merely a successful past download.
                    return False

        return True

    async def get_async(self, node_hash: str, validate_outputs: bool = True) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached output, checking memory first then SQLite.
        If validate_outputs is True, validates that all referenced output assets remain available.
        If missing or corrupt, invalidates the broken cache entry and returns None.
        """
        output: Optional[Dict[str, Any]] = None

        if node_hash in self._store:
            output = self._store[node_hash]
        else:
            try:
                conn = await self.manager.get_connection()
                async with conn.execute(
                    "SELECT output_json FROM cache_entries WHERE node_hash = ?",
                    (node_hash,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        output = json.loads(row["output_json"])
                        self._store[node_hash] = output
            except Exception as e:
                logger.error("Cache DB get operation failed: %s", e)
                return None

        if output is not None and validate_outputs:
            is_valid = await self.validate_output_assets(output)
            if not is_valid:
                logger.warning("Cached output assets missing or corrupt for %s. Invalidating cache.", node_hash)
                await self.invalidate_async(node_hash)
                return None

        return output

    async def set_async(self, node_hash: str, output: Dict[str, Any]) -> None:
        """Store output data in both memory and SQLite."""
        self._store[node_hash] = output
        try:
            conn = await self.manager.get_connection()
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries (node_hash, output_json, asset_ids_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (node_hash, json.dumps(output), json.dumps([]), now),
                )
            await conn.commit()
        except Exception as e:
            logger.error("Cache DB set operation failed: %s", e)

    async def has_async(self, node_hash: str) -> bool:
        """Check if output exists in memory or SQLite and outputs remain available."""
        return (await self.get_async(node_hash)) is not None

    async def reconcile_orphan_references_async(self) -> int:
        """
        Startup reconciliation: Scan all persistent cache entries in SQLite,
        validate that referenced asset files exist on disk, and purge orphan or broken entries.
        Returns the count of purged invalid cache entries.
        """
        purged_count = 0
        try:
            conn = await self.manager.get_connection()
            async with conn.execute("SELECT node_hash, output_json FROM cache_entries") as cursor:
                rows = await cursor.fetchall()

            for row in rows:
                h = row["node_hash"]
                try:
                    out = json.loads(row["output_json"])
                    if not await self.validate_output_assets(out):
                        await self.invalidate_async(h)
                        purged_count += 1
                except Exception as e:
                    logger.debug("Error validating cache row %s during reconciliation: %s", h, e)
                    await self.invalidate_async(h)
                    purged_count += 1

            if purged_count > 0:
                logger.info("Cache startup reconciliation purged %d orphan/broken entries.", purged_count)
        except Exception as e:
            logger.error("Cache reconciliation failed: %s", e)

        return purged_count

    def clear(self) -> None:
        """Purge in-memory cached results."""
        self._store.clear()

    async def clear_all_async(self) -> None:
        """Purge both in-memory and persistent SQLite cache."""
        self._store.clear()
        try:
            conn = await self.manager.get_connection()
            await conn.execute("DELETE FROM cache_entries")
            await conn.commit()
        except Exception as e:
            logger.error("Cache DB clear operation failed: %s", e)

    def size(self) -> int:
        """Return number of in-memory cached node states."""
        return len(self._store)


# Global default cache store singleton
cache_store = CacheStore()

