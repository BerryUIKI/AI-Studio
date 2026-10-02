"""Deterministic hashing and output result caching engine with SQLite persistence."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.storage.db import DatabaseManager, db_manager


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
) -> str:
    """
    Compute a deterministic port-aware SHA-256 hash representing a node's exact semantic state.
    NodeHash = SHA256(NodeType + SerializedCanonicalParams + OrderedPortBindings)

    OrderedPortBindings strictly associates input ports to upstream outputs:
    target_handle:source_handle:content_hash
    """
    hasher = hashlib.sha256()
    hasher.update(node_type.encode("utf-8"))

    # Canonicalize params: exclude transient secrets from hash
    clean_params = {k: v for k, v in params.items() if not k.lower().endswith("key")}
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

    def __init__(self, manager: Optional[DatabaseManager] = None) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self.manager = manager or db_manager

    def get(self, node_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached output data by node hash synchronously from memory."""
        return self._store.get(node_hash)

    def set(self, node_hash: str, output: Dict[str, Any]) -> None:
        """Store output data for a node hash in memory."""
        self._store[node_hash] = output

    def has(self, node_hash: str) -> bool:
        """Check if output for node hash is cached in memory."""
        return node_hash in self._store

    async def get_async(self, node_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached output, checking memory first then SQLite."""
        if node_hash in self._store:
            return self._store[node_hash]

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
                    return output
        except Exception:
            pass
        return None

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
        except Exception:
            pass

    async def has_async(self, node_hash: str) -> bool:
        """Check if output exists in memory or SQLite."""
        return (await self.get_async(node_hash)) is not None

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
        except Exception:
            pass

    def size(self) -> int:
        """Return number of in-memory cached node states."""
        return len(self._store)


# Global default cache store singleton
cache_store = CacheStore()
