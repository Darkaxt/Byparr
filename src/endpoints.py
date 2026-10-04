import asyncio
import contextlib
import time
import warnings
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Response, Route
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.admission import wait_for_disconnect
from src.challenge import challenge_present, solve_challenge
from src.consts import VERSION
from src.content import build_response_content
from src.models import (
    HealthcheckResponse,
    LinkRequest,
    LinkResponse,
    Solution,
)
from src.scripting import BrowserScript
from src.utils import (
    BrowserDepClass,
    TimeoutTimer,
    browser_admission,
    get_browser,
    logger,
    remaining_ms,
)

warnings.filterwarnings("ignore", category=SyntaxWarning)


router = APIRouter()

BrowserDep = Annotated[BrowserDepClass, Depends(get_browser, scope="function")]


@router.get("/ready")
async def readiness() -> dict[str, object]:
    """Report API readiness without browser launch or external traffic."""
    return {"status": "ok", "version": VERSION, "browser": browser_admission.status()}


@router.get("/", include_in_schema=False)
def read_root():
    """Redirect to /docs."""
    logger.debug("Redirecting to /docs")
    return RedirectResponse(url="/docs", status_code=301)


@router.get("/health")
async def health_check(sb: BrowserDep):
    """Health check endpoint."""
    health_check_request = await read_item(
        LinkRequest.model_construct(url="https://google.com"),
        sb,
    )

    if health_check_request.solution.status != HTTPStatus.OK:
        raise HTTPException(
            status_code=500,
            detail="Health check failed",
        )

    return HealthcheckResponse(user_agent=health_check_request.solution.user_agent)


@router.post("/v1")
async def read_item(
    request: LinkRequest, dep: BrowserDep, http_request: Request = None
) -> LinkResponse:
    """Handle POST requests."""
    if request.has_scripts:
        return await _run_scripted_request(request, dep, http_request)
    start_time = int(time.time() * 1000)
    timer = TimeoutTimer(duration=request.max_timeout)
    request.url = request.url.replace('"', "").strip()

    navigation_responses: list[Response] = []

    def capture_response(response: Response) -> None:
        if (
            response.request.is_navigation_request()
            and response.request.frame == dep.page.main_frame
        ):
            navigation_responses.append(response)

    dep.page.on("response", capture_response)
    try:
        challenge_detected, page_html, page_request = await _submit_navigation(
            dep, request, timer, navigation_responses
        )
        if navigation_responses:
            page_request = navigation_responses[-1]
    except (TimeoutError, PlaywrightTimeoutError) as e:
        logger.error("Timed out while loading the page or solving the challenge")
        raise HTTPException(
            status_code=408,
            detail="Timed out while loading the page or solving the challenge",
        ) from e
    except PlaywrightError as e:
        logger.error("Could not reach the target: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach the target: {e}",
        ) from e
    finally:
        dep.page.remove_listener("response", capture_response)
    if page_request is None:
        raise HTTPException(
            status_code=502, detail="Target navigation produced no HTTP response"
        )

    cookies = await dep.context.cookies()
    content_type, response_content = await build_response_content(
        dep.page,
        request,
        page_request,
        challenge_detected=challenge_detected,
        page_html=page_html,
    )

    user_agent = (
        page_request.request.headers.get("user-agent") or "" if page_request else ""
    )

    return LinkResponse(
        message="Success",
        solution=Solution(
            user_agent=user_agent,
            url=dep.page.url,
            status=page_request.status,
            cookies=cookies,
            headers=page_request.headers if page_request else {},
            response=response_content,
            content_type=content_type,
        ),
        start_timestamp=start_time,
    )


async def _run_scripted_request(
    request: LinkRequest, dep: BrowserDepClass, http_request: Request | None
) -> LinkResponse:
    """Enforce the API budget and react to client cancellation from the host."""
    operation = asyncio.create_task(_read_scripted_item(request, dep))
    disconnect = None
    try:
        async with asyncio.timeout(request.max_timeout):
            if http_request is not None:
                disconnect = asyncio.create_task(wait_for_disconnect(http_request))
                done, _ = await asyncio.wait(
                    (operation, disconnect), return_when=asyncio.FIRST_COMPLETED
                )
                if disconnect in done:
                    raise HTTPException(
                        499, "Client disconnected from browser operation"
                    )
            return await operation
    except TimeoutError as error:
        raise HTTPException(408, "Browser operation exceeded maxTimeout") from error
    finally:
        for task in (operation, disconnect):
            if task is not None:
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task


async def _read_scripted_item(
    request: LinkRequest, dep: BrowserDepClass
) -> LinkResponse:
    """Navigate, execute the supplied recipe and keep output distinct from HTML."""
    start_time = int(time.time() * 1000)
    timer = TimeoutTimer(duration=request.max_timeout)
    session = BrowserScript(dep, request, timer)
    responses: list[Response] = []

    def capture_navigation(response: Response) -> None:
        if (
            response.request.is_navigation_request()
            and response.request.frame == dep.page.main_frame
        ):
            responses.append(response)

    dep.page.on("response", capture_navigation)
    try:
        await session.install()
        challenged, html, target = await _submit_navigation(
            dep, request, timer, responses
        )
        target = responses[-1] if responses else target
        if target is None:
            raise HTTPException(502, "Target navigation produced no HTTP response")
        page_url = dep.page.url
        content_type, content = await build_response_content(
            dep.page, request, target, challenge_detected=challenged, page_html=html
        )
        result = await session.run()
        cookie_urls = [
            page_url,
            *(record["url"] for record in result.captures.values()),
        ]
        cookies = await dep.context.cookies(cookie_urls)
        user_agent = target.request.headers.get("user-agent", "")
        session.check_size(
            {
                "scriptResult": result.model_dump(by_alias=True),
                "cookies": cookies,
                "userAgent": user_agent,
            }
        )
        return LinkResponse(
            message="Success",
            start_timestamp=start_time,
            solution=Solution(
                url=page_url,
                status=target.status,
                headers=target.headers,
                response=content,
                content_type=content_type,
                user_agent=user_agent,
                cookies=cookies,
            ),
            scriptResult=result,
        )
    except PlaywrightTimeoutError as error:
        raise HTTPException(408, "Browser operation exceeded maxTimeout") from error
    except PlaywrightError as error:
        raise HTTPException(
            502, "Browser navigation or scripting initialization failed"
        ) from error
    finally:
        dep.page.remove_listener("response", capture_navigation)
        await session.close()


async def _submit_navigation(
    dep: BrowserDepClass,
    request: LinkRequest,
    timer: TimeoutTimer,
    navigation_responses: list[Response],
) -> tuple[bool, str | None, object]:
    """Perform preflight and at most one explicitly authorized POST replay."""
    if request.preflight_url:
        preflight = LinkRequest(
            url=request.preflight_url,
            max_timeout=request.max_timeout,
            block_media=request.block_media,
        )
        await setup_routes(preflight, dep)
        await _navigate_and_solve(dep, preflight, timer)
        navigation_responses.clear()
    await setup_routes(request, dep)
    result = await _navigate_and_solve(dep, request, timer)
    if request.cmd != "request.post" or not result[0]:
        return result
    if not request.replay_post_on_challenge:
        raise HTTPException(
            status_code=409,
            detail="POST encountered a challenge; it was not resubmitted. Use a preflightUrl or explicitly permit replayPostOnChallenge for a replay-safe operation.",
        )
    navigation_responses.clear()
    await setup_routes(request, dep)
    result = await _navigate_and_solve(dep, request, timer)
    if result[0]:
        raise HTTPException(
            status_code=409,
            detail="POST was challenged again after the single permitted replay; no further submission was made.",
        )
    return result


async def setup_routes(request: LinkRequest, dep: BrowserDep) -> None:
    """Override only the next main-frame navigation; keep challenge traffic intact."""
    if not (request.block_media or request.cmd == "request.post" or request.headers):
        return
    pending_navigation = True

    async def handle_route(route: Route) -> None:
        nonlocal pending_navigation
        if request.block_media and route.request.resource_type in (
            "image",
            "media",
            "font",
        ):
            await route.abort()
            return
        if (
            pending_navigation
            and route.request.is_navigation_request()
            and route.request.frame == dep.page.main_frame
        ):
            pending_navigation = False
            headers = {
                **route.request.headers,
                **{k.lower(): v for k, v in request.headers.items()},
            }
            if request.cmd == "request.post":
                headers.setdefault("content-type", "application/x-www-form-urlencoded")
                await route.continue_(
                    method="POST", post_data=request.post_data or "", headers=headers
                )
                return
            if request.headers:
                await route.continue_(headers=headers)
                return
        if request.has_scripts:
            await route.fallback()
        else:
            await route.continue_()

    await dep.page.route("**/*", handle_route)


async def _navigate_and_solve(
    dep: BrowserDep,
    request: LinkRequest,
    timer: TimeoutTimer,
) -> tuple[bool, str | None, object]:
    """Navigate to the URL, then solve a challenge or wait for network idle."""
    page_html: str | None = None
    page_request = await dep.page.goto(
        request.url,
        timeout=remaining_ms(timer),
        **({"wait_until": "domcontentloaded"} if request.has_scripts else {}),
    )
    await dep.page.wait_for_load_state(
        state="domcontentloaded", timeout=remaining_ms(timer)
    )

    if not await challenge_present(dep.page):
        if not request.has_scripts:
            await _wait_for_networkidle(dep, timer)
        page_html = await dep.page.content()
        return False, page_html, page_request

    await solve_challenge(dep.page, timer)
    if not request.has_scripts:
        await _wait_for_networkidle(dep, timer)
    return True, page_html, page_request


async def _wait_for_networkidle(dep: BrowserDep, timer: TimeoutTimer) -> None:
    """Wait for network idle, tolerating post-DOM-load stalls."""
    try:
        await dep.page.wait_for_load_state("networkidle", timeout=remaining_ms(timer))
    except PlaywrightTimeoutError:
        logger.info(
            "networkidle timed out after domcontentloaded; continuing with loaded page"
        )
