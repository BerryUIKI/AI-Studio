"""Deterministic hashing and output result caching engine."""

import hashlib
import json
from typing import Any, Dict, Optional


def compute_node_hash(node_type: str, params: Dict[str, Any], parent_hashes: list[str]) -> str:
    """
    Compute a deterministic SHA-256 hash representing a node's exact state.
    NodeHash = SHA256(NodeType + SerializedParams + SortedParentHashes)
    """
    hasher = hashlib.sha256()
    hasher.update(node_type.encode("utf-8"))

    # Serialize parameters with sorted keys for deterministic encoding
    params_str = json.dumps(params, sort_keys=True, default=str)
    hasher.update(params_str.encode("utf-8"))

    # Concatenate upstream parent hashes in deterministic sorted order
    for parent_hash in sorted(parent_hashes):
        hasher.update(parent_hash.encode("utf-8"))

    return hasher.hexdigest()


class CacheStore:
    """Thread-safe in-memory cache store for node execution outputs."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, node_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached output data by node hash."""
        return self._store.get(node_hash)

    def set(self, node_hash: str, output: Dict[str, Any]) -> None:
        """Store output data for a node hash."""
        self._store[node_hash] = output

    def has(self, node_hash: str) -> bool:
        """Check if output for node hash is cached."""
        return node_hash in self._store

    def clear(self) -> None:
        """Purge all cached results."""
        self._store.clear()

    def size(self) -> int:
        """Return number of cached node states."""
        return len(self._store)


# Global default cache store singleton
cache_store = CacheStore()
