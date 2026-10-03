"""Admission must precede browser creation and release on every exit path."""

import asyncio
import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.testclient import TestClient

from main import app
from src.utils import BrowserDepClass, get_browser
from tests.post_test import dependency


@pytest.mark.asyncio
@pytest.mark.parametrize("scripted", [True, False])
async def test_only_scripted_contexts_bypass_csp_and_block_workers(scripted):
    """Trusted scripting enables CSP bypass and authoritative capture; ordinary contexts do not."""
    request = Request({"type": "http", "state": {"byparr_scripted": scripted}})
    browser = AsyncMock()
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=browser)
    manager.__aexit__ = AsyncMock(return_value=False)
    with patch("src.utils.InvisiblePlaywright", return_value=manager) as factory:
        operation = get_browser(http_request=request)
        await anext(operation)
        await operation.aclose()
    if scripted:
        browser.new_context.assert_awaited_once_with(
            bypass_csp=True, service_workers="block"
        )
    else:
        browser.new_context.assert_awaited_once_with()
    assert "dom.serviceWorkers.enabled" not in factory.call_args.kwargs["extra_prefs"]


@pytest.mark.asyncio
async def test_busy_browser_is_rejected_and_success_releases_admission():
    """One admitted operation rejects another without launching another browser."""
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=AsyncMock())
    manager.__aexit__ = AsyncMock(return_value=False)
    with patch("src.utils.InvisiblePlaywright", return_value=manager) as factory:
        first = get_browser()
        await anext(first)
        other = get_browser()
        with pytest.raises(HTTPException) as error:
            await anext(other)
        assert error.value.status_code == 429  # noqa: PLR2004 - HTTP admission response
        assert factory.call_count == 1
        await first.aclose()
        next_request = get_browser()
        await anext(next_request)
        await next_request.aclose()
    assert manager.__aexit__.await_count == 2  # noqa: PLR2004 - two admitted requests


@pytest.mark.asyncio
async def test_launch_failure_releases_admission():
    """A failed launch cannot permanently occupy admission."""
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(side_effect=RuntimeError("fixture"))
    manager.__aexit__ = AsyncMock(return_value=False)
    with patch("src.utils.InvisiblePlaywright", return_value=manager):
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await anext(get_browser())
        assert manager.__aenter__.await_count == 2  # noqa: PLR2004 - both reached launch


@pytest.mark.asyncio
async def test_cancelled_setup_releases_admission():
    """Cancellation during page creation closes the browser and frees admission."""
    entered = asyncio.Event()
    never = asyncio.Event()
    browser = AsyncMock()

    async def blocked_page() -> None:
        entered.set()
        await never.wait()

    browser.new_context.return_value.new_page.side_effect = blocked_page
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=browser)
    manager.__aexit__ = AsyncMock(return_value=False)
    with patch("src.utils.InvisiblePlaywright", return_value=manager):
        task = asyncio.create_task(anext(get_browser()))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        manager.__aexit__.assert_awaited_once()
        browser.new_context.return_value.new_page.side_effect = None
        next_request = get_browser()
        await anext(next_request)
        await next_request.aclose()


def test_readiness_does_not_start_a_browser():
    """Monitoring is cheap and independent from browser/network health probes."""
    with patch("src.utils.InvisiblePlaywright") as factory, TestClient(app) as client:
        result = client.get("/ready")
    assert result.status_code == 200  # noqa: PLR2004 - HTTP readiness response
    factory.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_precedes_http_response():
    """A completed response must mean the prior browser has been cleaned up."""
    cleaned = False

    async def fixture_browser() -> AsyncGenerator[BrowserDepClass]:
        nonlocal cleaned
        try:
            yield dependency()
        finally:
            cleaned = True

    body = json.dumps({"url": "https://example.test"}).encode()
    sent_after_cleanup = []
    received = False
    never = asyncio.Event()

    async def receive() -> dict:
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body}
        await never.wait()
        return {"type": "http.disconnect"}

    async def send(message) -> None:
        if message["type"] == "http.response.start":
            sent_after_cleanup.append(cleaned)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/v1",
        "raw_path": b"/v1",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "server": ("example.test", 80),
        "client": ("127.0.0.1", 1234),
    }
    app.dependency_overrides[get_browser] = fixture_browser
    try:
        with patch("src.endpoints.challenge_present", AsyncMock(return_value=False)):
            await app(scope, receive, send)
    finally:
        app.dependency_overrides.clear()
    assert sent_after_cleanup == [True]
