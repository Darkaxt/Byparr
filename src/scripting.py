"""Request-owned browser scripting, native input and pre-transfer captures."""

import asyncio
import contextlib
import json
import re
import secrets
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from fastapi import HTTPException
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Request, Response, Route
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models import MAX_SCRIPT_BYTES, LinkRequest, ScriptResult
from src.utils import BrowserDepClass, TimeoutTimer, remaining_ms

MAX_RESULT_BYTES = 1024 * 1024
MAX_CAPTURES = 8
MAX_PAGES = 2
MAX_SELECTOR_LENGTH = 4096


class CaptureOptions(BaseModel):
    """Explicit, origin-safe matching for one named browser event."""

    model_config = ConfigDict(extra="forbid")
    method: str = Field(pattern=r"^[A-Z]{1,16}$")
    url: str | None = Field(default=None, max_length=8192)
    url_prefix: str | None = Field(default=None, alias="urlPrefix", max_length=8192)
    abort: bool = False

    @model_validator(mode="after")
    def validate_match(self) -> CaptureOptions:
        """Validate that a URL prefix describes an actual HTTP origin and path."""
        if (self.url is None) == (self.url_prefix is None):
            message = "Capture needs either url or urlPrefix"
            raise ValueError(message)
        target = urlsplit(self.url or self.url_prefix or "")
        if (
            target.scheme not in {"http", "https"}
            or not target.hostname
            or target.username
            or target.password
            or target.fragment
        ):
            message = "Capture needs an HTTP(S) URL without credentials/fragment"
            raise ValueError(message)
        _ = target.port  # Validate malformed ports.
        return self

    def matches(self, request: Request) -> bool:
        """Never mistake a lookalike hostname for the selected origin."""
        if request.method != self.method:
            return False
        if self.url is not None:
            return request.url == self.url
        wanted, actual = urlsplit(self.url_prefix or ""), urlsplit(request.url)
        return (
            origin(wanted) == origin(actual)
            and actual.path.startswith(wanted.path)
            and (not wanted.query or actual.query.startswith(wanted.query))
        )


def origin(url) -> tuple[str, str | None, int]:
    """Normalize the scheme, hostname and effective port."""
    return url.scheme, url.hostname, url.port or (443 if url.scheme == "https" else 80)


@dataclass
class Capture:
    """Host state remains valid when the page's execution context disappears."""

    kind: Literal["request", "response"]
    options: CaptureOptions
    future: asyncio.Future
    claimed: bool = False


class BrowserScript:
    """One scripting operation; all state and listeners die with its request."""

    def __init__(self, dep: BrowserDepClass, request: LinkRequest, timer: TimeoutTimer):
        """Initialize bounded host state for one browser operation."""
        self.dep, self.request, self.timer = dep, request, timer
        self.captures: dict[str, Capture] = {}
        self.terminal_name: str | None = None
        self.terminal = asyncio.get_running_loop().create_future()
        self.response_tasks: set[asyncio.Task] = set()
        self.script_task: asyncio.Task | None = None
        nonce = secrets.token_hex(24)
        self.init_attribute = "data-byparr-" + nonce
        self.binding_name = "__byparr_main_" + nonce
        self.execute_name = "__byparr_execute_" + nonce
        self.helper_tasks: set[asyncio.Task] = set()
        self.closing = False

    async def install(self) -> None:
        """Expose helpers and initialization before any target navigation."""
        if self.request.init_script is not None:
            try:
                await self.dep.page.evaluate(
                    "body => { new Function(body); }", self.request.init_script
                )
            except PlaywrightError as error:
                raise HTTPException(
                    422, "Invalid initialization script syntax"
                ) from error
        if self.request.script is not None:
            try:
                await self.dep.page.evaluate(
                    "body => { new Function('return (' + body + '\\n);'); }",
                    self.request.script,
                )
            except PlaywrightError as error:
                raise HTTPException(422, "Invalid browser script syntax") from error
        await self.dep.context.expose_binding(self.binding_name, self.invoke)
        await self.dep.context.route("**/*", self.route)
        self.dep.context.on("response", self.on_response)
        self.dep.context.on("page", self.on_page)
        bootstrap = """(() => {
            if (window !== window.top) return;
            const call = (operation, ...args) => window[/*__BINDING__*/]({operation, args});
            Object.defineProperty(window, 'byparr', {value: Object.freeze({
                click: (selector, frameSelector = null) => call('click', selector, frameSelector),
                watchRequest: (name, options) => call('watchRequest', name, options),
                watchResponse: (name, options) => call('watchResponse', name, options),
                waitFor: name => call('waitFor', name),
                finishWith: name => call('finishWith', name)
            }), configurable: false});
            let initFailed = false;
            if (location.origin === new URL(/*__TARGET__*/).origin) {
                try { /*__INIT__*/ } catch (error) { initFailed = true; }
            }
            const initialized = () => document.documentElement.setAttribute(
                /*__ATTRIBUTE__*/, initFailed ? 'failed' : 'ready'
            );
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initialized, {once: true});
            } else initialized();
            Object.defineProperty(window, /*__EXECUTE__*/, {value: async args => {
                const fn = (/*__SCRIPT__*/);
                if (typeof fn !== 'function') throw new Error('script must be a function');
                const value = await fn(args);
                const text = JSON.stringify(value, (key, item) => {
                    if (typeof item === 'number' && !Number.isFinite(item))
                        throw new Error('script output must be finite JSON');
                    return item;
                });
                if (text === undefined || new TextEncoder().encode(text).length > /*__LIMIT__*/)
                    throw new Error('script output must be bounded JSON');
                return text;
            }});
        })();"""
        replacements = {
            "TARGET": json.dumps(self.request.url),
            "BINDING": json.dumps(self.binding_name),
            "INIT": self.request.init_script or "",
            "ATTRIBUTE": json.dumps(self.init_attribute),
            "EXECUTE": json.dumps(self.execute_name),
            "SCRIPT": self.request.script or "() => null",
            "LIMIT": str(MAX_RESULT_BYTES),
        }
        # Substitute once so literal placeholder text in caller code stays literal.
        source = re.sub(
            r"/\*__(TARGET|BINDING|INIT|ATTRIBUTE|EXECUTE|SCRIPT|LIMIT)__\*/",
            lambda match: replacements[match[1]],
            bootstrap,
        )
        await self.dep.page.add_init_script(source)

    def on_page(self, _page) -> None:
        """Bound pages without launching any additional browser process."""
        if len(self.dep.context.pages) > MAX_PAGES:
            self.fail(HTTPException(413, "Script exceeded the two-page limit"))

    def fail(self, error: Exception) -> None:
        """Wake the operation on a host-observed failure."""
        if not self.terminal.done():
            self.terminal.set_exception(error)

    async def invoke(self, source, payload):
        """Own native helper work until request cleanup and context destruction."""
        task = asyncio.current_task()
        self.helper_tasks.add(task)
        try:
            if (
                self.closing
                or len(self.check_size(payload).encode("utf-8")) > MAX_SCRIPT_BYTES
            ):
                message = (
                    "Browser helper arguments exceed the limit or operation closed"
                )
                raise ValueError(message)
            try:
                return await self.call(source, payload)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                message = "Browser helper failed"
                raise ValueError(message) from error
        finally:
            self.helper_tasks.discard(task)

    async def call(self, source, payload):
        """Dispatch only browser helpers; never evaluate server-side code."""
        if (
            source["page"] != self.dep.page
            or source["frame"] != self.dep.page.main_frame
        ):
            message = "Helpers are available only in the requested main document"
            raise ValueError(message)
        operation, args = payload["operation"], payload["args"]
        if operation == "click":
            return await self.click(*args)
        if operation in {"watchRequest", "watchResponse"}:
            return self.watch(operation, *args)
        if operation in {"waitFor", "finishWith"}:
            name = args[0]
            if name not in self.captures:
                message = "Unknown capture name"
                raise ValueError(message)
            capture = self.captures[name]
            if operation == "waitFor":
                return await asyncio.shield(capture.future)
            if self.terminal_name is not None:
                message = "A terminal capture has already been selected"
                raise ValueError(message)
            self.terminal_name = name
            capture.future.add_done_callback(self.complete_terminal)
            if capture.future.done():
                self.complete_terminal(capture.future)
            return name
        message = "Unsupported browser helper"
        raise ValueError(message)

    async def click(self, selector, frame_selector) -> None:
        """Perform strict native input in the main document or selected frame."""
        if not isinstance(selector, str) or len(selector) > MAX_SELECTOR_LENGTH:
            message = "Invalid click selector"
            raise ValueError(message)
        target = self.dep.page
        if frame_selector is not None:
            if (
                not isinstance(frame_selector, str)
                or len(frame_selector) > MAX_SELECTOR_LENGTH
            ):
                message = "Invalid frame selector"
                raise ValueError(message)
            target = target.frame_locator(frame_selector)
        await target.locator(selector).click(timeout=remaining_ms(self.timer))

    def watch(self, operation, name, options) -> str:
        """Register once, separately from awaiting the actual browser event."""
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name)
            or name in self.captures
            or len(self.captures) >= MAX_CAPTURES
        ):
            message = "Capture name is invalid, duplicated or exceeds the limit"
            raise ValueError(message)
        parsed = CaptureOptions.model_validate(options)
        kind = "request" if operation == "watchRequest" else "response"
        if kind == "response" and parsed.abort:
            message = "Only request capture can abort before transfer"
            raise ValueError(message)
        self.captures[name] = Capture(
            kind, parsed, asyncio.get_running_loop().create_future()
        )
        return name

    def complete_terminal(self, future: asyncio.Future) -> None:
        """Publish the explicitly selected capture outside the page context."""
        if self.terminal.done() or future.cancelled():
            return
        error = future.exception()
        if error is not None:
            self.terminal.set_exception(error)
        else:
            self.terminal.set_result(future.result())

    async def route(self, route: Route) -> None:
        """Capture and abort before continuing a matching attachment request."""
        if self.closing:
            if any(
                capture.options.abort and capture.options.matches(route.request)
                for capture in self.captures.values()
            ):
                await route.abort()
            else:
                await route.fallback()
            return
        matches = [
            capture
            for capture in self.captures.values()
            if capture.kind == "request"
            and not capture.claimed
            and capture.options.matches(route.request)
        ]
        for capture in matches:
            capture.claimed = True
        try:
            record = None
            if matches:
                record = {
                    "kind": "request",
                    "url": route.request.url,
                    "method": route.request.method,
                    "requestHeaders": await route.request.all_headers(),
                    "aborted": any(capture.options.abort for capture in matches),
                }
                self.check_size(record)
            if record and record["aborted"]:
                await route.abort()
            else:
                await route.fallback()
            if record:
                self.publish(matches, record)
        except Exception as error:
            self.fail(HTTPException(502, "Browser request capture failed"))
            for capture in matches:
                if not capture.future.done():
                    capture.future.set_exception(error)

    @staticmethod
    def publish(captures: list[Capture], record: dict) -> None:
        """Publish only to captures still owned by a live operation."""
        for capture in captures:
            if not capture.future.done():
                capture.future.set_result(record)

    def on_response(self, response: Response) -> None:
        """Claim the first matching response before scheduling body collection."""
        matches = [
            capture
            for capture in self.captures.values()
            if capture.kind == "response"
            and not capture.claimed
            and capture.options.matches(response.request)
        ]
        if matches:
            for capture in matches:
                capture.claimed = True
            task = asyncio.create_task(self.collect_response(response, matches))
            self.response_tasks.add(task)
            task.add_done_callback(self.response_tasks.discard)

    async def collect_response(
        self, response: Response, captures: list[Capture]
    ) -> None:
        """Preserve actual failure status/body without returning private logs."""
        try:
            headers = await response.all_headers()
            if int(headers.get("content-length", "0")) > MAX_RESULT_BYTES:
                raise HTTPException(413, "Captured response exceeds the output limit")  # noqa: TRY301 - validate at response boundary
            body = await response.body()
            if len(body) > MAX_RESULT_BYTES:
                raise HTTPException(413, "Captured response exceeds the output limit")  # noqa: TRY301 - validate at response boundary
            text = body.decode("utf-8", errors="replace")
            try:
                value = json.loads(text)
            except ValueError:
                value = text
            record = {
                "kind": "response",
                "url": response.url,
                "method": response.request.method,
                "status": response.status,
                "headers": headers,
                "body": value,
                "requestHeaders": await response.request.all_headers(),
            }
            self.check_size(record)
            self.publish(captures, record)
        except Exception as error:
            controlled = (
                error
                if isinstance(error, HTTPException)
                else HTTPException(502, "Browser response capture failed")
            )
            for capture in captures:
                if not capture.future.done():
                    capture.future.set_exception(controlled)
            self.fail(controlled)

    @staticmethod
    def check_size(value) -> str:
        """Keep structured results bounded and finite JSON."""
        try:
            text = json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (ValueError, TypeError) as error:
            raise HTTPException(422, "Script output must be finite JSON") from error
        if len(text.encode("utf-8")) > MAX_RESULT_BYTES:
            raise HTTPException(413, "Script output exceeds 1 MiB")
        return text

    async def run(self) -> ScriptResult:
        """Await script output or a host-retained terminal capture."""
        root = self.dep.page.locator(f"html[{self.init_attribute}]")
        await root.wait_for(state="attached", timeout=remaining_ms(self.timer))
        if await root.get_attribute(self.init_attribute) == "failed":
            raise HTTPException(422, "Browser initialization script failed")
        if self.terminal.done():
            self.terminal.result()
        value = None
        if self.request.script is not None:
            self.script_task = asyncio.create_task(self.dispatch())
            done, _ = await asyncio.wait(
                (self.script_task, self.terminal), return_when=asyncio.FIRST_COMPLETED
            )
            if self.terminal in done:
                value = self.terminal.result()
            else:
                try:
                    value = json.loads(self.script_task.result())
                except PlaywrightError as error:
                    if self.terminal.done():
                        value = self.terminal.result()
                    elif (
                        self.terminal_name is not None
                        and "Execution context was destroyed" in str(error)
                    ):
                        value = await asyncio.shield(self.terminal)
                    else:
                        partial = ScriptResult(
                            captures=self.completed_captures(),
                            terminalCapture=self.terminal_name,
                        )
                        self.check_size(partial.model_dump(by_alias=True))
                        raise HTTPException(
                            422,
                            {
                                "message": "Browser script failed; no terminal capture completed",
                                "scriptResult": partial.model_dump(by_alias=True),
                            },
                        ) from error
                if self.terminal_name is not None:
                    value = await asyncio.shield(self.terminal)
        if self.response_tasks:
            await asyncio.gather(*self.response_tasks)
        result = ScriptResult(
            value=value,
            captures=self.completed_captures(),
            terminalCapture=self.terminal_name,
        )
        self.check_size(result.model_dump(by_alias=True))
        return result

    async def dispatch(self) -> str:
        """Await the function installed before site scripts in the main document."""
        return await self.dep.page.evaluate(
            "([name, args]) => window[name](args)",
            [self.execute_name, self.request.script_args],
        )

    def completed_captures(self) -> dict[str, dict]:
        """Retain completed browser evidence even when the recipe rejects it."""
        return {
            name: capture.future.result()
            for name, capture in self.captures.items()
            if capture.future.done()
            and not capture.future.cancelled()
            and capture.future.exception() is None
        }

    async def close(self) -> None:
        """Remove listeners/routes and consume or cancel request-owned tasks."""
        self.dep.context.remove_listener("response", self.on_response)
        self.dep.context.remove_listener("page", self.on_page)
        # Keep the abort guard until get_browser destroys the context.
        self.closing = True
        tasks = [*self.response_tasks, *self.helper_tasks]
        if self.script_task is not None:
            tasks.append(self.script_task)
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        for future in (
            self.terminal,
            *(capture.future for capture in self.captures.values()),
        ):
            if future.done() and not future.cancelled():
                future.exception()
            elif not future.done():
                future.cancel()
