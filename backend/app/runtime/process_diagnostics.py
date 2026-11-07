"""Bounded, redacted process diagnostics; missing output never proves readiness."""

import io
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import subprocess
import threading

_SECRETS = re.compile(
    r"(?i)((?:api[_-]?key|access[_-]?token|password|authorization|token)[\"']?\s*[=:]\s*)"
    r"(\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s\"',;]+)"
)
_AUTHORIZATION = re.compile(r"(?i)(authorization[\"']?\s*[=:]\s*[\"']?)(?:Bearer|Basic)\s+[^\s\"',;]+")
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s\"',;]+")
_PROVIDER_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")


def redact_log(line: str) -> str:
    line = _AUTHORIZATION.sub(r"\1[REDACTED]", line)
    line = _BEARER.sub("Bearer [REDACTED]", line)
    line = _SECRETS.sub(r"\1[REDACTED]", line)
    return _PROVIDER_KEY.sub("[REDACTED]", line)


class ProcessDiagnostics:
    def __init__(self, path: Path, max_bytes: int = 512 * 1024) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self.reader: threading.Thread | None = None
        self.error: str | None = None

    def attach(self, process: subprocess.Popen[bytes]) -> None:
        stream = process.stdout
        if not isinstance(stream, io.IOBase):
            return
        handler = None
        self.error = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(self.path, maxBytes=self.max_bytes, backupCount=2, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
        except OSError as error:
            self.error = redact_log(f"Engine output could not be retained: {error}")

        def consume() -> None:
            try:
                while True:
                    data = stream.readline(4096)
                    if not data:
                        break
                    line = redact_log(data.decode("utf-8", errors="replace").rstrip())
                    if handler is not None:
                        handler.handle(logging.LogRecord("engine", logging.INFO, "", 0, line, (), None))
            finally:
                stream.close()
                if handler is not None:
                    handler.close()

        self.reader = threading.Thread(target=consume, name="engine-diagnostics", daemon=True)
        self.reader.start()

    def recent(self, lines: int = 100) -> list[str]:
        lines = min(max(lines, 0), 1000)
        if not lines:
            return []
        if not self.path.is_file():
            return [self.error] if self.error else []
        try:
            with self.path.open("rb") as source:
                source.seek(0, 2)
                offset = max(0, source.tell() - self.max_bytes)
                source.seek(offset)
                if offset:
                    source.readline(4096)
                text = source.read(self.max_bytes).decode("utf-8", errors="replace")
            result = [redact_log(line) for line in text.splitlines()[-lines:]]
            return (result + [self.error])[-lines:] if self.error else result
        except OSError:
            return []
