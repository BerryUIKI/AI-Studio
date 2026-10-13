"""User-defined provider descriptors; credentials are stored separately."""

import hashlib
import json
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class CustomProviderSpec(BaseModel):
    id: str = Field(pattern=r"^custom-[a-z0-9][a-z0-9-]{0,62}$")
    name: str = Field(min_length=1, max_length=80)
    endpoint: str = Field(max_length=2048)
    models: list[str] = Field(min_length=1, max_length=32)
    actions: list[Literal["txt2img", "img2img", "inpaint", "upscale"]] = Field(
        min_length=1, max_length=4
    )
    mode: Literal["rest", "javascript", "python", "python_sdk"] = "rest"
    source: str = Field(default="", max_length=131072)
    body_template: dict[str, Any] = Field(
        default_factory=lambda: {
            "model": "{{model}}",
            "prompt": "{{prompt}}",
            "size": "{{width}}x{{height}}",
            "n": 1,
        }
    )
    result_path: str = Field(
        default="data.0.url",
        pattern=r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*$",
        max_length=200,
    )
    response_format: Literal["url", "b64_json"] = "url"
    auth: Literal["bearer", "header", "none"] = "bearer"
    auth_header: str = Field(
        default="Authorization", pattern=r"^[A-Za-z][A-Za-z0-9-]{0,63}$"
    )
    request_timeout: int = Field(default=120, ge=1, le=180)
    worker_timeout: int = Field(default=150, ge=1, le=180)
    max_requests: int = Field(default=4, ge=1, le=16)
    requirements: str = Field(default="", max_length=16384)
    sdk_allow_credentials: bool = False
    upload_disclosure: str = Field(
        default="Prompts and selected input images are sent to this user-configured platform.",
        min_length=1,
        max_length=1000,
    )

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.hostname
        ):
            raise ValueError(
                "Endpoint must not contain credentials, query parameters or fragments"
            )
        if parsed.scheme != "https" and not (
            parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError(
                "Use HTTPS, or HTTP for an explicitly configured loopback platform"
            )
        return value

    @field_validator("models")
    @classmethod
    def validate_models(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 160 for value in values) or len(
            set(values)
        ) != len(values):
            raise ValueError(
                "Models must be unique, nonempty identifiers of at most 160 characters"
            )
        return values

    @field_validator("requirements")
    @classmethod
    def validate_requirements(cls, value: str) -> str:
        for line in value.splitlines():
            if line.strip() and not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9_.+!-]+(?: +--hash=sha256:[a-f0-9]{64})+",
                line.strip(),
            ):
                raise ValueError(
                    "Each dependency needs an exact version and SHA256 hash; URLs and installer options are not allowed"
                )
        return value.strip()

    @property
    def revision(self) -> str:
        payload = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class SaveCustomProviderRequest(BaseModel):
    spec: CustomProviderSpec
    approve_execution: bool = False


class CustomProviderRecord(BaseModel):
    spec: CustomProviderSpec
    trusted_revision: str | None = None

    @property
    def execution_trusted(self) -> bool:
        return self.trusted_revision == self.spec.revision
