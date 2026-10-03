"""Focused POST contracts; real browser coverage lives in browser_integration.py."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.testclient import TestClient

from main import app
from src.content import build_response_content
from src.endpoints import read_item, setup_routes
from src.models import LinkRequest
from src.utils import BrowserDepClass, get_browser


def dependency(status=200, content_type="text/html", body=b"done"):
    """Model only the browser interfaces needed for focused contracts."""
    page = AsyncMock()
    page.url = "https://example.test/post"
    page.main_frame = MagicMock()
    page.on = MagicMock()
    page.remove_listener = MagicMock()
    response = MagicMock(status=status, headers={"content-type": content_type})
    response.request.headers = {"user-agent": "Browser/1"}
    response.body = AsyncMock(return_value=body)
    response.text = AsyncMock(return_value=body.decode())
    page.goto.return_value = response
    page.content.return_value = "<html>done</html>"
    context = AsyncMock()
    context.cookies.return_value = []
    return BrowserDepClass(page, context)


def navigation(dep, url="https://example.test/post", *, main=True):
    """Build a main-frame or child-frame intercepted request."""
    route = MagicMock()
    route.request.url = url
    route.request.is_navigation_request.return_value = True
    route.request.frame = dep.page.main_frame if main else MagicMock()
    route.request.resource_type = "document"
    route.request.headers = {"accept": "text/html", "user-agent": "Browser/1"}
    route.continue_ = AsyncMock()
    route.abort = AsyncMock()
    return route


def test_post_body_and_validation():
    """Validate body aliases, bounds and same-origin preflight."""
    request = LinkRequest(
        url="https://example.test/post", cmd="request.post", postData="x=%26"
    )
    assert request.post_data == "x=%26"
    for payload in [
        {"cmd": "sessions.create"},
        {"postData": "x"},
        {"cmd": "request.post", "postData": "x" * (1024 * 1024 + 1)},
        {"cmd": "request.post", "postData": "é" * (512 * 1024 + 1)},
        {"cmd": "request.post", "preflightUrl": "https://other.test/"},
        {"headers": {"Cookie": "caller=owned"}},
        {"headers": {"X-Probe": "value\r\ninjected=yes"}},
    ]:
        with pytest.raises(ValidationError):
            LinkRequest(url="https://example.test/post", **payload)


@pytest.mark.asyncio
async def test_get_cookies_only_does_not_read_content():
    """The GET cookies-only contract skips all content retrieval."""
    dep = dependency()
    content_type, body = await build_response_content(
        dep.page,
        LinkRequest(url="https://example.test", returnOnlyCookies=True),
        dep.page.goto.return_value,
        challenge_detected=False,
        page_html=None,
    )
    assert content_type == "text/html"
    assert body == ""
    dep.page.content.assert_not_awaited()
    dep.page.goto.return_value.body.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_pdf_uses_original_response_without_get_refetch():
    """POST content retrieval cannot turn into another target request."""
    dep = dependency(content_type="application/pdf", body=b"%PDF-fixture")
    content_type, body = await build_response_content(
        dep.page,
        LinkRequest(url="https://example.test", cmd="request.post"),
        dep.page.goto.return_value,
        challenge_detected=False,
        page_html=None,
    )
    assert content_type == "application/pdf"
    assert body == "JVBERi1maXh0dXJl"
    dep.page.request.fetch.assert_not_awaited()


def test_invalid_command_is_api_validation_error():
    """Reject unsupported commands before allocating browser resources."""

    async def unexpected_browser() -> None:
        message = "Validation must happen before browser creation"
        raise AssertionError(message)

    app.dependency_overrides[get_browser] = unexpected_browser
    try:
        with TestClient(app) as client:
            result = client.post(
                "/v1", json={"cmd": "request.delete", "url": "https://example.test"}
            )
    finally:
        app.dependency_overrides.clear()
    assert result.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_only_initial_main_navigation_is_posted():
    """Leave frames and later navigations untouched."""
    dep = dependency()
    await setup_routes(
        LinkRequest(
            url="https://example.test/post", cmd="request.post", postData="x=%26"
        ),
        dep,
    )
    handler = dep.page.route.await_args.args[1]
    frame = navigation(dep, main=False)
    await handler(frame)
    frame.continue_.assert_awaited_once_with()
    first = navigation(dep)
    await handler(first)
    kwargs = first.continue_.await_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["post_data"] == "x=%26"
    assert kwargs["headers"]["content-type"] == "application/x-www-form-urlencoded"
    assert kwargs["headers"]["user-agent"] == "Browser/1"
    again = navigation(dep)
    await handler(again)
    again.continue_.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_actual_status_and_json_body():
    """Preserve JSON response text and the actual upstream error status."""
    with patch("src.endpoints.challenge_present", AsyncMock(return_value=False)):
        result = await read_item(
            LinkRequest(
                url="https://example.test/post", cmd="request.post", postData="{}"
            ),
            dependency(422, "application/json", b'{"error":"invalid"}'),
        )
    assert result.solution.status == HTTPStatus.UNPROCESSABLE_ENTITY
    assert result.solution.content_type == "application/json"
    assert result.solution.response == '{"error":"invalid"}'


@pytest.mark.asyncio
async def test_challenged_post_never_silently_replays():
    """Require caller permission before issuing an additional POST."""
    dep = dependency()
    with (
        patch("src.endpoints.challenge_present", AsyncMock(return_value=True)),
        patch("src.endpoints.solve_challenge", AsyncMock()),
        pytest.raises(HTTPException) as error,
    ):
        await read_item(
            LinkRequest(
                url="https://example.test/post", cmd="request.post", postData="x=y"
            ),
            dep,
        )
    assert error.value.status_code == HTTPStatus.CONFLICT
    assert dep.page.goto.await_count == 1


@pytest.mark.asyncio
async def test_explicit_replay_is_limited_to_one():
    """A second challenge cannot create an unbounded replay loop."""
    dep = dependency()
    with (
        patch("src.endpoints.challenge_present", AsyncMock(return_value=True)),
        patch("src.endpoints.solve_challenge", AsyncMock()),
        pytest.raises(HTTPException) as error,
    ):
        await read_item(
            LinkRequest(
                url="https://example.test/post",
                cmd="request.post",
                postData="x=y",
                replayPostOnChallenge=True,
            ),
            dep,
        )
    assert error.value.status_code == HTTPStatus.CONFLICT
    assert dep.page.goto.await_count == 2  # noqa: PLR2004 - one original plus one replay
