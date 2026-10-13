"""Atomic provider registry, independent of code execution and credential storage."""

import json
import os
import tempfile
import threading
from pathlib import Path

from app.schemas.custom_provider import CustomProviderRecord, CustomProviderSpec
from app.storage.db import get_default_data_dir


class CustomProviderRegistry:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir
        self._lock = threading.RLock()

    @property
    def directory(self) -> Path:
        return (self.data_dir or get_default_data_dir()) / "custom-providers"

    def _path(self, identifier: str) -> Path:
        import re

        if not re.fullmatch(r"custom-[a-z0-9][a-z0-9-]{0,62}", identifier):
            raise ValueError("Invalid custom provider identifier")
        return self.directory / f"{identifier}.json"

    def list(self) -> list[CustomProviderRecord]:
        with self._lock:
            if not self.directory.exists():
                return []
            records = []
            for path in sorted(self.directory.glob("custom-*.json")):
                try:
                    record = CustomProviderRecord.model_validate_json(
                        path.read_text(encoding="utf-8")
                    )
                    if path.name == f"{record.spec.id}.json":
                        records.append(record)
                except (ValueError, OSError):
                    continue
            return records

    def get(self, identifier: str) -> CustomProviderRecord:
        with self._lock:
            path = self._path(identifier)
            try:
                record = CustomProviderRecord.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
            except FileNotFoundError:
                raise LookupError("Custom provider not found") from None
            if record.spec.id != identifier:
                raise ValueError("Provider record identity does not match its path")
            return record

    def save(
        self, spec: CustomProviderSpec, approve_execution: bool = False
    ) -> CustomProviderRecord:
        with self._lock:
            old = None
            try:
                old = self.get(spec.id)
            except LookupError:
                pass
            trusted = (
                spec.revision
                if approve_execution
                else old.trusted_revision
                if old
                else None
            )
            record = CustomProviderRecord(spec=spec, trusted_revision=trusted)
            self.directory.mkdir(parents=True, exist_ok=True)
            descriptor, staging = tempfile.mkstemp(
                prefix=".provider-", suffix=".tmp", dir=self.directory
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(record.model_dump_json(indent=2))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(staging, self._path(spec.id))
            finally:
                Path(staging).unlink(missing_ok=True)
            return record

    def delete(self, identifier: str) -> None:
        with self._lock:
            self.get(identifier)
            self._path(identifier).unlink()


custom_provider_registry = CustomProviderRegistry()
