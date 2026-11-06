"""Installed-browser proof for cookie/reload documents that outlive network idle."""

import asyncio
import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi import HTTPException

from src.endpoints import read_item
from src.models import LinkRequest
from src.utils import browser_admission, get_browser

# Standalone real-browser fixture, following existing wire-test conventions.
# ruff: noqa: ANN002,ANN003,D102,D103,C901,PLR0912,PLR0915,PLR2004,T201,PT018,PT017,TRY003

BASE = "http://127.0.0.1:18085"
pending = threading.Event()
release = threading.Event()
eo_pending = threading.Event()
eo_release = threading.Event()
records = []


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, body, status=200, headers=None):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            self.wfile.write(data)

    def interstitial(self, destination):
        # This delay is the reproduced target protocol, not client synchronization.
        return f"""<html><head><script>
        document.cookie='__tst_status=fixture; path=/';
        document.cookie='EO_Bot_Ssid=fixture; path=/';
        setTimeout(() => {{ location.href={json.dumps(destination)}; }},1200);
        </script></head><body></body></html>"""

    def edgeone(self, code):
        return f"""<title>Security Verification</title><body>
        <div id="captcha"><iframe id="tcaptcha_iframe_eo" src="http://localhost:18085/widget/{code}"></iframe></div>
        <p>Protected by Tencent Cloud EdgeOne</p></body>"""

    def do_GET(self):
        if self.path == "/favicon.ico":
            self.reply("", 204)
            return
        records.append(("GET", self.path))
        if self.path.startswith("/edgeone/"):
            code = self.path.rsplit("/", 1)[1]
            self.reply(self.edgeone(code))
        elif self.path.startswith("/widget/"):
            code = self.path.rsplit("/", 1)[1]
            destination = "/edgeone/repeat" if code == "repeat" else "/final/" + code
            self.reply(f"""<div id="verifyCheckbox" style="width:32px;height:32px;background:#ddd"
            onclick="if(event.isTrusted)fetch('/edgeone-click').then(()=>parent.location.href='http://127.0.0.1:18085{destination}');">Verify</div>""")
        elif self.path == "/edgeone-click":
            self.reply("acknowledged")
        elif self.path == "/edgeone-cancel":
            self.reply("""<title>Security Verification</title><body><div id="captcha"></div>
            <p>Protected by Tencent Cloud EdgeOne</p><script>setTimeout(()=>{
            const f=document.createElement('iframe');f.id='tcaptcha_iframe_eo';
            f.src='http://localhost:18085/eo-pending';document.querySelector('#captcha').append(f);},1200);</script></body>""")
        elif self.path == "/eo-pending":
            eo_pending.set()
            eo_release.wait()
            self.reply("cancelled widget")
        elif self.path == "/edgeone-loading":
            self.reply(
                "<title>Security Verification</title><body><div id='captcha'></div><p>Protected by Tencent Cloud EdgeOne</p></body>"
            )
        elif self.path == "/same":
            if "EO_Bot_Ssid=fixture" in self.headers.get("Cookie", ""):
                self.reply(
                    "<title>Same URL target</title><body>requested-package</body>",
                    headers={"X-Final-Document": "yes"},
                )
            else:
                self.reply(self.interstitial("/same"))
        elif self.path.startswith("/start/"):
            self.reply(self.interstitial("/final/" + self.path.rsplit("/", 1)[1]))
        elif self.path == "/blocked":
            self.reply(
                self.interstitial("/final/200"),
                headers={"Content-Security-Policy": "script-src 'none'"},
            )
        elif self.path == "/cancel":
            self.reply(self.interstitial("/pending"))
        elif self.path == "/pending":
            pending.set()
            release.wait()
            self.reply("<title>Cancelled transition must not succeed</title>")
        else:
            code = int(self.path.rsplit("/", 1)[1])
            self.reply(
                f"<title>Actual target {code}</title><body>requested-package</body>",
                code,
                {
                    "X-Final-Document": "yes",
                    "Set-Cookie": "edgeone_clear=fixture; Path=/",
                },
            )

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        records.append(("POST", self.path))
        if (
            self.path == "/edgeone-post"
            and "edgeone_clear=fixture" not in self.headers.get("Cookie", "")
        ):
            self.reply(self.edgeone(200))
            return
        if self.path == "/edgeone-post" or "EO_Bot_Ssid=fixture" in self.headers.get(
            "Cookie", ""
        ):
            self.reply("<title>Actual POST target</title><body>accepted-once</body>")
        else:
            self.reply(self.interstitial("/final/200"))


async def operation(path, **kwargs):
    async with contextlib.aclosing(get_browser()) as resources:
        dep = await anext(resources)
        return await read_item(
            LinkRequest(url=BASE + path, maxTimeout=15000, **kwargs), dep
        )


async def verify():
    for code in (200, 503):
        result = await operation(f"/start/{code}")
        assert result.solution.url == BASE + f"/final/{code}", result.solution.url
        assert result.solution.status == code
        assert result.solution.headers["x-final-document"] == "yes"
        assert "requested-package" in result.solution.response
        print(
            f"PASS scheduled cookie navigation returns matching final URL/status/body {code}",
            flush=True,
        )

    result = await operation("/same")
    assert result.solution.url == BASE + "/same"
    assert result.solution.status == 200
    assert result.solution.headers["x-final-document"] == "yes"
    assert "requested-package" in result.solution.response
    print("PASS same-URL reload waits for the new document", flush=True)

    for code in (200, 503):
        result = await operation(f"/edgeone/{code}")
        assert result.solution.url == BASE + f"/final/{code}"
        assert result.solution.status == code
        assert "requested-package" in result.solution.response
    print(
        "PASS EdgeOne native click in cross-origin widget returns final 200/503",
        flush=True,
    )
    result = await operation("/edgeone/200", script="() => ({verified:true})")
    assert result.script_result.value == {"verified": True}
    assert result.solution.url == BASE + "/final/200"
    print("PASS scripting starts only after EdgeOne document verification", flush=True)

    before = records.count(("GET", "/edgeone-click"))
    try:
        await operation("/edgeone/repeat")
    except HTTPException as error:
        assert error.status_code == 408
    else:
        raise AssertionError("Unresolved EdgeOne verification returned success")
    assert records.count(("GET", "/edgeone-click")) - before == 1
    print(
        "PASS persistent EdgeOne verification receives one native input only",
        flush=True,
    )

    # A recognized but non-executing interstitial must consume only its API budget.
    async with contextlib.aclosing(get_browser()) as resources:
        dep = await anext(resources)
        try:
            await read_item(LinkRequest(url=BASE + "/blocked", maxTimeout=1500), dep)
        except HTTPException as error:
            assert error.status_code == 408
        else:
            raise AssertionError("Blocked interstitial returned successful content")
    print(
        "PASS non-executing challenge fails explicitly within request budget",
        flush=True,
    )
    async with contextlib.aclosing(get_browser()) as resources:
        dep = await anext(resources)
        try:
            await read_item(
                LinkRequest(url=BASE + "/edgeone-loading", maxTimeout=1000), dep
            )
        except HTTPException as error:
            assert error.status_code == 408
        else:
            raise AssertionError("Unloaded EdgeOne widget returned successful content")
    print(
        "PASS unavailable EdgeOne widget fails explicitly without repeated input",
        flush=True,
    )

    task = asyncio.create_task(operation("/cancel"))
    try:
        await asyncio.to_thread(pending.wait)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        assert task.cancelled()
        assert browser_admission.status()["active"] is False
        result = await operation("/final/200")
        assert "requested-package" in result.solution.response
    finally:
        release.set()
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    print(
        "PASS cancellation during pending navigation releases browser before next request",
        flush=True,
    )

    task = asyncio.create_task(operation("/edgeone-cancel"))
    try:
        await asyncio.to_thread(eo_pending.wait)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        assert task.cancelled() and browser_admission.status()["active"] is False
        assert "requested-package" in (await operation("/final/200")).solution.response
    finally:
        eo_release.set()
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    print("PASS cancellation cleans pending EdgeOne input/navigation tasks", flush=True)

    for path, permission, expected in (
        ("/post", False, 1),
        ("/post", True, 2),
        ("/edgeone-post", False, 1),
        ("/edgeone-post", True, 2),
    ):
        before = records.count(("POST", path))
        try:
            result = await operation(
                path,
                cmd="request.post",
                postData="x=one",
                replayPostOnChallenge=permission,
            )
        except HTTPException as error:
            assert not permission and error.status_code == 409
        else:
            assert permission and "accepted-once" in result.solution.response
        assert records.count(("POST", path)) - before == expected
    print(
        "PASS cookie and EdgeOne interstitials respect explicit one-replay POST permission",
        flush=True,
    )


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 18085), Fixture)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        asyncio.run(verify())
    finally:
        release.set()
        eo_release.set()
        server.shutdown()
        server.server_close()
