from __future__ import annotations

import json
import re
import time
from http.client import INTERNAL_SERVER_ERROR
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from playwright.sync_api import Cookie
from pydantic import (
    BaseModel,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel

from src import consts

MS_PER_SECOND = 1000
MAX_HEADER_BYTES = 16384
MAX_SCRIPT_BYTES = 65536


class LinkRequest(BaseModel):
    model_config = {"populate_by_name": True}
    request_id: UUID | None = Field(default=None, alias="requestId")

    cmd: Literal["request.get", "request.post"] = Field(
        default="request.get",
        description="Browser navigation command: request.get or request.post.",
    )
    url: str = Field(pattern=r"^https?://", default="https://")
    post_data: str | None = Field(
        default=None, alias="postData", max_length=1024 * 1024
    )
    headers: dict[str, str] = Field(default_factory=dict, max_length=32)
    preflight_url: str | None = Field(default=None, alias="preflightUrl")
    replay_post_on_challenge: bool = Field(default=False, alias="replayPostOnChallenge")
    init_script: str | None = Field(
        default=None, alias="initScript", max_length=MAX_SCRIPT_BYTES
    )
    script: str | None = Field(default=None, max_length=MAX_SCRIPT_BYTES)
    script_args: Any = Field(default=None, alias="scriptArgs")

    @property
    def has_scripts(self) -> bool:
        """Whether this operation needs the optional scripting lifecycle."""
        return self.init_script is not None or self.script is not None

    @model_validator(mode="after")
    def validate_scripts(self) -> LinkRequest:
        """Bound optional source/arguments before allocating a browser."""
        if self.script_args is not None and self.script is None:
            message = "scriptArgs requires script"
            raise ValueError(message)
        for source in (self.init_script, self.script):
            if source is not None and len(source.encode("utf-8")) > MAX_SCRIPT_BYTES:
                message = "Script exceeds 64 KiB UTF-8"
                raise ValueError(message)
        try:
            arguments = json.dumps(
                self.script_args, ensure_ascii=False, allow_nan=False
            )
        except (TypeError, ValueError) as error:
            message = "scriptArgs must be finite JSON"
            raise ValueError(message) from error
        if len(arguments.encode("utf-8")) > MAX_SCRIPT_BYTES:
            message = "scriptArgs exceeds 64 KiB UTF-8"
            raise ValueError(message)
        if self.has_scripts and self.max_timeout <= 0:
            message = "Scripting requires a positive maxTimeout"
            raise ValueError(message)
        return self

    @model_validator(mode="after")
    def validate_post(self) -> LinkRequest:
        """Reject ambiguous bodies and unsafe browser-header overrides."""
        if self.cmd != "request.post" and (
            self.post_data is not None
            or self.preflight_url
            or self.replay_post_on_challenge
        ):
            message = "POST options require cmd=request.post"
            raise ValueError(message)
        if (
            self.post_data is not None
            and len(self.post_data.encode("utf-8")) > 1024 * 1024
        ):
            message = "postData exceeds 1 MiB"
            raise ValueError(message)
        if self.preflight_url:
            target, preflight = urlsplit(self.url), urlsplit(self.preflight_url)

            def origin(url) -> tuple[str, str | None, int]:
                return (
                    url.scheme.lower(),
                    url.hostname,
                    url.port or (443 if url.scheme == "https" else 80),
                )

            if (
                origin(target) != origin(preflight)
                or preflight.username
                or preflight.password
            ):
                message = "preflightUrl must use the target's HTTP(S) origin"
                raise ValueError(message)
        forbidden = {
            "cookie",
            "host",
            "content-length",
            "user-agent",
            "connection",
            "transfer-encoding",
        }
        if (
            sum(len(k.encode()) + len(v.encode()) for k, v in self.headers.items())
            > MAX_HEADER_BYTES
        ):
            message = "headers exceed 16 KiB"
            raise ValueError(message)
        for key, value in self.headers.items():
            if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) or any(
                c in value for c in "\r\n\0"
            ):
                message = "Invalid header name or value"
                raise ValueError(message)
            if key.lower() in forbidden or key.lower().startswith(("sec-", "proxy-")):
                message = "Browser-owned headers cannot be overridden"
                raise ValueError(message)
        return self

    max_timeout: int = Field(
        default=60,
        alias="maxTimeout",
        description=(
            "Maximum timeout for resolving the anti-bot challenge. Values below 1000 "
            "are treated as seconds; values of 1000 or more as milliseconds, matching "
            "FlareSolverr's maxTimeout parameter."
        ),
    )
    block_media: bool = Field(
        default=consts.BLOCK_MEDIA,
        alias="blockMedia",
        description="Block image, media, and font resources from loading.",
    )
    return_only_cookies: bool = Field(
        default=consts.RETURN_ONLY_COOKIES,
        alias="returnOnlyCookies",
        description="Return only cookies, skip the page HTML content in the response.",
    )

    @field_validator("max_timeout")
    @classmethod
    def normalize_max_timeout(cls, value: int) -> int:
        """Normalize FlareSolverr-style millisecond values to seconds."""
        if value >= MS_PER_SECOND:
            return value // MS_PER_SECOND
        return value


class HealthcheckResponse(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    msg: str = "Byparr is working!"
    version: str = consts.VERSION
    user_agent: str


class Solution(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    url: str
    status: int
    cookies: list[Cookie] = []
    user_agent: str = ""
    headers: dict[str, Any] = {}
    response: str = ""
    content_type: str = Field(default="text/html", alias="contentType")


class ScriptResult(BaseModel):
    """Structured browser output, separate from navigation HTML/status."""

    value: Any = None
    captures: dict[str, dict[str, Any]] = Field(default_factory=dict)
    terminal_capture: str | None = Field(default=None, alias="terminalCapture")


class LinkResponse(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    status: str = "ok"
    message: str
    solution: Solution
    start_timestamp: int
    end_timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    version: str = consts.VERSION
    script_result: ScriptResult | None = Field(default=None, alias="scriptResult")
    request_id: UUID | None = Field(default=None, alias="requestId")

    @model_serializer(mode="wrap")
    def serialize_optional_script_result(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        """Omit absent scripting while preserving explicit null script values."""
        value = handler(self)
        if self.script_result is None:
            value.pop("scriptResult", None)
            value.pop("script_result", None)
        if self.request_id is None:
            value.pop("requestId", None)
            value.pop("request_id", None)
        return value

    @classmethod
    def invalid(cls, url: str) -> LinkResponse:
        """
        Return an invalid LinkResponse with default error values.

        This method is used to generate a response indicating an invalid request.
        """
        return cls(
            status="error",
            message="Invalid request",
            solution=Solution(url=url, status=INTERNAL_SERVER_ERROR),
            start_timestamp=int(time.time() * 1000),
        )
