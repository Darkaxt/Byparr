"""Focused contracts for optional scripting; live browser proof is separate."""

from collections.abc import AsyncGenerator
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from playwright.async_api import Error as PlaywrightError
from pydantic import ValidationError
from starlette.testclient import TestClient

from main import app
from src.models import LinkRequest, ScriptResult
from src.scripting import BrowserScript, CaptureOptions
from src.utils import BrowserDepClass, TimeoutTimer, get_browser
from tests.post_test import dependency


def test_optional_scripts_and_json_arguments_are_preserved():
    """The optional interface must not silently ignore caller scripts."""
    request = LinkRequest(
        url="https://example.test/page",
        initScript="window.beforeSite = true;",
        script="async args => ({fileId: args.fileId})",
        scriptArgs={"fileId": "123", "nested": [True, None]},
    )
    assert request.init_script == "window.beforeSite = true;"
    assert request.script_args == {"fileId": "123", "nested": [True, None]}
    assert request.has_scripts


@pytest.mark.parametrize(
    "payload",
    [
        {"scriptArgs": {"missing": "script"}},
        {"script": "x" * (65536 + 1)},
        {"initScript": "é" * (32768 + 1)},
        {"script": "args => args", "scriptArgs": "x" * 65536},
        {"script": "args => args", "scriptArgs": float("inf")},
        {"script": "() => null", "maxTimeout": 0},
    ],
)
def test_invalid_script_options_are_rejected(payload):
    """Reject ambiguous, unbounded and non-JSON requests before execution."""
    with pytest.raises(ValidationError):
        LinkRequest(url="https://example.test/page", **payload)


def test_invalid_script_request_never_allocates_browser():
    """Middleware validation must precede browser dependency allocation."""

    async def unexpected_browser() -> None:
        message = "Invalid script request allocated a browser"
        raise AssertionError(message)

    app.dependency_overrides[get_browser] = unexpected_browser
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1", json={"url": "https://example.test", "scriptArgs": {"x": 1}}
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_script_null_remains_a_structured_json_value():
    """Optional response omission must not discard an explicit JSON null."""
    session = MagicMock()
    session.install = AsyncMock()
    session.run = AsyncMock(return_value=ScriptResult(value=None))
    session.close = AsyncMock()

    async def fixture_browser() -> AsyncGenerator[BrowserDepClass]:
        yield dependency()

    app.dependency_overrides[get_browser] = fixture_browser
    try:
        with (
            patch("src.endpoints.BrowserScript", return_value=session),
            patch("src.endpoints.challenge_present", AsyncMock(return_value=False)),
            TestClient(app) as client,
        ):
            response = client.post(
                "/v1", json={"url": "https://example.test", "script": "() => null"}
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == HTTPStatus.OK
    assert "value" in response.json()["scriptResult"]
    assert response.json()["scriptResult"]["value"] is None


def test_capture_prefix_cannot_match_another_origin():
    """Prefix routing must reject hostname lookalikes and different ports."""
    options = CaptureOptions(method="GET", urlPrefix="https://downloads.example/file/")
    for url, expected in [
        ("https://downloads.example/file/123", True),
        ("https://downloads.example.evil/file/123", False),
        ("https://downloads.example:444/file/123", False),
        ("http://downloads.example/file/123", False),
    ]:
        assert options.matches(MagicMock(method="GET", url=url)) is expected


@pytest.mark.asyncio
async def test_script_failure_preserves_completed_error_response():
    """A recipe rejection must not hide an already observed upstream failure."""
    dep = dependency()
    dep.context.remove_listener = MagicMock()
    dep.page.locator = MagicMock(return_value=AsyncMock())
    session = BrowserScript(
        dep,
        LinkRequest(url="https://example.test", script="() => null"),
        TimeoutTimer(duration=60),
    )
    session.watch(
        "watchResponse",
        "failure",
        {"method": "POST", "url": "https://example.test/resolve"},
    )
    record = {
        "kind": "response",
        "url": "https://example.test/resolve",
        "status": 400,
        "body": {"errorCode": -51},
    }
    session.captures["failure"].future.set_result(record)
    dep.page.evaluate = AsyncMock(side_effect=PlaywrightError("private script detail"))
    try:
        with pytest.raises(HTTPException) as failure:
            await session.run()
        assert failure.value.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert failure.value.detail["scriptResult"]["captures"]["failure"] == record
        assert "private script detail" not in str(failure.value.detail)
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_native_helper_rejects_child_frames():
    """The host refuses native input from a child even if it learns the name."""
    dep = dependency()
    dep.context.remove_listener = MagicMock()
    session = BrowserScript(
        dep,
        LinkRequest(url="https://example.test", script="() => null"),
        TimeoutTimer(duration=60),
    )
    payload = {
        "operation": "watchRequest",
        "args": ["download", {"method": "GET", "url": "https://example.test/file"}],
    }
    await session.invoke({"page": dep.page, "frame": dep.page.main_frame}, payload)
    assert "download" in session.captures
    with pytest.raises(ValueError, match="Browser helper failed"):
        await session.invoke({"page": dep.page, "frame": MagicMock()}, payload)
    assert not session.helper_tasks
    await session.close()


@pytest.mark.asyncio
async def test_cleanup_retains_attachment_abort_until_context_destruction():
    """Late attachment traffic cannot escape between script and browser cleanup."""
    dep = dependency()
    dep.context.remove_listener = MagicMock()
    session = BrowserScript(
        dep,
        LinkRequest(url="https://example.test", script="() => null"),
        TimeoutTimer(duration=60),
    )
    session.watch(
        "watchRequest",
        "download",
        {"method": "GET", "url": "https://example.test/file", "abort": True},
    )
    await session.close()
    route = AsyncMock()
    route.request = MagicMock(method="GET", url="https://example.test/file")
    await session.route(route)
    route.abort.assert_awaited_once()
    route.fallback.assert_not_awaited()
    dep.context.unroute.assert_not_awaited()
