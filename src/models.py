from __future__ import annotations

import re
import time
from http.client import INTERNAL_SERVER_ERROR
from typing import Any, Literal
from urllib.parse import urlsplit

from playwright.sync_api import Cookie
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from src import consts

MS_PER_SECOND = 1000
MAX_HEADER_BYTES = 16384


class LinkRequest(BaseModel):
    model_config = {"populate_by_name": True}

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


class LinkResponse(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}
    status: str = "ok"
    message: str
    solution: Solution
    start_timestamp: int
    end_timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    version: str = consts.VERSION

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
