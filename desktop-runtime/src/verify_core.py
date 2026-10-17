"""Validate a prepared runtime without shell-dependent inline Python quoting."""

import pathlib
import sys

assert sys.version_info >= (3, 10)
assert pathlib.Path(sys.prefix).resolve() == pathlib.Path(sys.argv[1]).resolve()

import aiosqlite  # noqa: F401
import fastapi  # noqa: F401
import httpx  # noqa: F401
import multipart  # noqa: F401
import PIL  # noqa: F401
import pydantic
import quickjs  # noqa: F401
import uvicorn  # noqa: F401

assert int(pydantic.__version__.split(".")[0]) >= 2
assert "torch" not in sys.modules
