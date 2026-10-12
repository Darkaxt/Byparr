"""Focused regressions for the compatible October 12 upstream changes."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import main as application
from src.endpoints import read_item
from src.models import LinkRequest
from src.utils import LOG_LEVEL, get_browser
from tests.post_test import dependency


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "final_url", ["https://example.test/start", "https://final.test/"]
)
async def test_normal_cookies_only_include_requested_and_final_urls(final_url):
    """Third-party cookies must not poison the consumer's clearance jar."""
    dep = dependency()
    dep.page.url = final_url
    with patch("src.endpoints.challenge_present", new=AsyncMock(return_value=False)):
        await read_item(LinkRequest(url="https://example.test/start"), dep)
    expected = ["https://example.test/start"]
    if final_url not in expected:
        expected.append(final_url)
    dep.context.cookies.assert_awaited_once_with(expected)


@pytest.mark.asyncio
async def test_http_navigation_pref_preserves_transactional_browser_lifecycle():
    """HTTPS-First is disabled without removing the single-browser transaction."""
    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=AsyncMock())
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=browser)
    session.__aexit__ = AsyncMock(return_value=False)
    launcher = MagicMock(return_value=session)
    with patch("src.utils.InvisiblePlaywright", launcher):
        async for _ in get_browser():
            pass
    assert launcher.call_args.kwargs["extra_prefs"]["dom.security.https_first"] is False
    browser.new_context.return_value.close.assert_awaited_once()
    session.__aexit__.assert_awaited_once()


def test_uvicorn_log_level_is_normalized():
    """Uvicorn receives the configured level in its expected string form."""
    assert logging.getLevelName(LOG_LEVEL).lower() == application.LOG_LEVEL_NAME
