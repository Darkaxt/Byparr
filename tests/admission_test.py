"""Admission must precede browser creation and release on every exit path."""

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.testclient import TestClient

from main import app
from src.admission import BrowserAdmission
from src.utils import BrowserDepClass, get_browser
from tests.post_test import dependency


def test_handoff_cannot_be_overtaken_and_queue_is_bounded():
    """Ownership moves atomically to an existing waiter, never a new arrival."""

    # Futures belong to a loop, while registration/handoff themselves never await.
    async def exercise() -> None:
        admission = BrowserAdmission(2)
        first, second, third = admission.enter(), admission.enter(), admission.enter()
        with pytest.raises(HTTPException) as error:
            admission.enter()
        assert error.value.status_code == 503  # noqa: PLR2004 - backlog full
        admission.leave(first)
        newcomer = admission.enter()
        assert admission.owner is second
        assert not third.done()
        assert not newcomer.done()
        admission.leave(second)
        assert admission.owner is third
        assert not newcomer.done()
        admission.leave(third)
        assert admission.owner is newcomer
        admission.leave(newcomer)
        assert admission.status() == {"active": False, "queued": 0, "queueLimit": 2}

    asyncio.run(exercise())


@pytest.mark.asyncio
@pytest.mark.parametrize("handoff", [False, True])
async def test_cancelled_waiter_and_handoff_release_without_submission(handoff):
    """Task cancellation removes a pending ticket, including just-granted ownership."""
    admission = BrowserAdmission(2)
    owner = admission.enter()
    entered = asyncio.Event()
    submitted = False

    async def waiter() -> None:
        nonlocal submitted
        entered.set()
        async with admission.transaction():
            submitted = True

    task = asyncio.create_task(waiter())
    await entered.wait()
    if handoff:
        admission.leave(owner)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    if not handoff:
        admission.leave(owner)
    assert not submitted
    assert admission.status()["queued"] == 0
    async with admission.transaction():
        assert admission.status()["active"]
    assert not admission.status()["active"]


@pytest.mark.asyncio
@pytest.mark.parametrize("handoff", [False, True])
async def test_disconnected_waiter_never_submits(handoff):
    """The actual disconnect wins over simultaneous ownership handoff."""
    admission = BrowserAdmission(2)
    owner = admission.enter()
    receiving = asyncio.Event()
    messages = asyncio.Queue()

    async def receive() -> dict:
        receiving.set()
        return await messages.get()

    request = Request({"type": "http"}, receive)
    submitted = False

    async def waiter() -> None:
        nonlocal submitted
        async with admission.transaction(request):
            submitted = True

    task = asyncio.create_task(waiter())
    await receiving.wait()
    messages.put_nowait({"type": "http.disconnect"})
    if handoff:
        admission.leave(owner)
    with pytest.raises(HTTPException) as error:
        await task
    assert error.value.status_code == 499  # noqa: PLR2004 - actual disconnect
    if not handoff:
        admission.leave(owner)
    assert not submitted
    assert not admission.status()["active"]
    assert admission.status()["queued"] == 0


@pytest.mark.asyncio
async def test_next_browser_waits_for_driver_exit():
    """Context close alone cannot release admission before driver cleanup."""
    exiting, allow_exit, waiting = asyncio.Event(), asyncio.Event(), asyncio.Event()
    manager = MagicMock()
    browser = AsyncMock()
    manager.__aenter__ = AsyncMock(return_value=browser)

    async def driver_exit(*_args: object) -> bool:
        exiting.set()
        await allow_exit.wait()
        return False

    manager.__aexit__ = AsyncMock(side_effect=driver_exit)
    with patch("src.utils.InvisiblePlaywright", return_value=manager) as factory:
        first, second = get_browser(), get_browser()
        await anext(first)
        closing = asyncio.create_task(first.aclose())
        await exiting.wait()

        async def begin() -> BrowserDepClass:
            waiting.set()
            return await anext(second)

        next_task = asyncio.create_task(begin())
        await waiting.wait()
        assert factory.call_count == 1
        assert not next_task.done()
        allow_exit.set()
        await closing
        await next_task
        await second.aclose()
    assert browser.new_context.return_value.close.await_count == 2  # noqa: PLR2004


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
async def test_browser_requests_wait_fifo_without_extra_launches():
    """Waiting requests launch once, in order, after the preceding cleanup."""
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=AsyncMock())
    manager.__aexit__ = AsyncMock(return_value=False)
    with patch("src.utils.InvisiblePlaywright", return_value=manager) as factory:
        first = get_browser()
        await anext(first)
        second, third = get_browser(), get_browser()
        started = asyncio.Queue()

        async def begin(operation) -> BrowserDepClass:
            started.put_nowait(None)
            return await anext(operation)

        second_task = asyncio.create_task(begin(second))
        await started.get()
        third_task = asyncio.create_task(begin(third))
        await started.get()
        try:
            assert not second_task.done()
            assert not third_task.done()
            assert factory.call_count == 1
            await first.aclose()
            await second_task
            assert not third_task.done()
            await second.aclose()
            await third_task
            await third.aclose()
        finally:
            for task in (second_task, third_task):
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError, HTTPException):
                    await task
            for operation in (first, second, third):
                await operation.aclose()
    assert manager.__aexit__.await_count == 3  # noqa: PLR2004 - three transactions


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
