import asyncio
import time
from asyncio import sleep
from contextlib import suppress

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import FloatRect, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.utils import TimeoutTimer, logger, remaining_ms

# Background scripts also occur on successfully loaded Cloudflare-protected pages.
# Unknown challenge-platform scripts remain conservative interstitial indicators.
CF_INTERSTITIAL_INDICATORS_SELECTORS = [
    (
        'script[src*="/cdn-cgi/challenge-platform/"]'
        ':not([src*="/scripts/precursor/"]):not([src*="/scripts/jsd/"])'
    ),
]

__all__ = [
    "CF_INTERSTITIAL_INDICATORS_SELECTORS",
    "challenge_present",
    "edgeone_verification_present",
    "javascript_redirect_present",
    "solve_challenge",
    "solve_edgeone",
]

POLL_INTERVAL = 0.25
CLICK_SETTLE = 1.5
CLICK_COOLDOWN = 4
PROBE_INTERVAL = 0.5
TOKEN_READ_TIMEOUT = 1000
BOX_READ_TIMEOUT = 1000
CHECKBOX_INSET = 25
TURNSTILE_INPUT = 'input[name="cf-turnstile-response"]'
WIDGET_ANCESTOR_DEPTHS = (1, 2, 3, 4)
WIDGET_MIN_WIDTH = 40
WIDGET_MIN_HEIGHT = 20
WIDGET_MAX_HEIGHT = 120


async def challenge_present(page: Page) -> bool:
    """Report whether the Cloudflare interstitial is up."""
    try:
        for selector in CF_INTERSTITIAL_INDICATORS_SELECTORS:
            if await page.locator(selector).count():
                return True
    except PlaywrightError:
        # Navigation can destroy a context between observations; that is not
        # evidence that the challenge has cleared.
        return True
    return False


async def javascript_redirect_present(page: Page) -> bool:
    """Recognize the empty cookie/reload interstitial, without executing its code."""
    body = page.locator("body")
    if await body.count() == 0 or await body.locator(":scope > *").count():
        return False
    if (await body.text_content() or "").strip():
        return False
    # Native text_content works under CSP. Bulk evaluation is blocked, while
    # :has-text deliberately excludes script-node contents in Playwright.
    scripts = page.locator("script:not([src])")
    for index in range(await scripts.count()):
        source = await scripts.nth(index).text_content() or ""
        if all(
            marker in source
            for marker in ("__tst_status", "EO_Bot_Ssid", "setTimeout", "location")
        ):
            return True
    return False


async def edgeone_verification_present(page: Page) -> bool:
    """Recognize the observed verification document, including its loading state."""
    if await page.title() != "Security Verification":
        return False
    if await page.locator("#captcha").count() == 0:
        return False
    text = await page.locator("body").text_content() or ""
    return "Protected by Tencent Cloud EdgeOne" in " ".join(text.split())


async def solve_edgeone(
    page: Page, timer: TimeoutTimer, committed: asyncio.Event
) -> None:
    """Activate the verified native control once, or follow natural navigation."""
    checkbox = page.frame_locator("#tcaptcha_iframe_eo").locator("#verifyCheckbox")
    click = asyncio.create_task(checkbox.click(timeout=remaining_ms(timer)))
    navigation = asyncio.create_task(committed.wait())
    try:
        done, _ = await asyncio.wait(
            (click, navigation), return_when=asyncio.FIRST_COMPLETED
        )
        if navigation not in done:
            await click
            logger.info("Activated EdgeOne verification; awaiting its navigation")
            await asyncio.wait_for(navigation, timeout=timer.remaining())
    finally:
        for task in (click, navigation):
            if not task.done():
                task.cancel()
        await asyncio.gather(click, navigation, return_exceptions=True)


async def widget_box(page: Page) -> FloatRect | None:
    """Measure the widget container with locators; running page scripts resets the challenge."""
    for depth in WIDGET_ANCESTOR_DEPTHS:
        widget = page.locator(f"{TURNSTILE_INPUT} >> xpath=ancestor::div[{depth}]")
        with suppress(PlaywrightError, PlaywrightTimeoutError):
            if await widget.count() == 0:
                continue
            box = await widget.first.bounding_box(timeout=BOX_READ_TIMEOUT)
            if (
                box
                and box["width"] > WIDGET_MIN_WIDTH
                and WIDGET_MIN_HEIGHT < box["height"] < WIDGET_MAX_HEIGHT
            ):
                return box
    return None


async def click_checkbox(page: Page) -> bool:
    """Click the checkbox through its container, leaving its closed shadow root alone."""
    box = await widget_box(page)
    if box is None:
        return False
    await page.mouse.move(box["x"] + CHECKBOX_INSET, box["y"] + box["height"] / 2)
    try:
        await page.mouse.down()
    finally:
        await page.mouse.up()
    return True


async def checkbox_already_answered(page: Page) -> bool:
    """Report whether Turnstile has already filled in its response token."""
    token = page.locator(TURNSTILE_INPUT)
    with suppress(PlaywrightError, PlaywrightTimeoutError):
        if await token.count() > 0:
            return bool(await token.first.input_value(timeout=TOKEN_READ_TIMEOUT))
    return False


async def challenge_is_gone(page: Page) -> bool:
    """Confirm the interstitial is really gone and not just between navigations."""
    if await challenge_present(page):
        return False
    await sleep(POLL_INTERVAL)
    return not await challenge_present(page)


async def solve_challenge(page: Page, timer: TimeoutTimer) -> None:
    """Wait out the interstitial, clicking its checkbox whenever one is offered."""
    logger.info("Challenge detected, waiting for it to clear...")
    clicks = 0
    next_click = 0.0
    while True:
        if await challenge_is_gone(page):
            logger.debug("Challenge cleared.")
            if clicks:
                await sleep(min(CLICK_SETTLE, timer.remaining()))
            return

        if time.perf_counter() >= next_click:
            landed = False
            with suppress(PlaywrightError, PlaywrightTimeoutError):
                landed = not await checkbox_already_answered(
                    page
                ) and await click_checkbox(page)
            if landed:
                clicks += 1
                logger.info("Clicked the challenge checkbox (attempt %d).", clicks)
            next_click = time.perf_counter() + (
                CLICK_COOLDOWN if landed else PROBE_INTERVAL
            )

        if timer.remaining() <= 0:
            break
        await sleep(POLL_INTERVAL)

    message = "Challenge still present when the request budget ran out"
    raise TimeoutError(message)
