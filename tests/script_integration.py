"""Sequential real-browser proof for scripts, input, capture and cancellation."""

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from starlette.testclient import TestClient

from main import app

# Standalone protocol fixtures intentionally use literal statuses and concise
# wire assertions. No external website or challenge service is simulated as live.
# ruff: noqa: D102,D103,ANN002,ANN003,PLR2004,PT018,T201,PLR0915

records = []
held = threading.Event()
release = threading.Event()
signals = {"disconnect": None}


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, body, status=200, content_type="text/html"):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if self.path == "/bridge":
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'unsafe-inline'; connect-src 'none'; frame-src 'self'",
            )
        self.send_header("Set-Cookie", "fixture=browser; Path=/; HttpOnly")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        records.append(("GET", self.path))
        if self.path == "/bindings":
            self.reply("""<script>
                window.polluted = ['byparr','__byparr_call','__playwright__binding__',
                    '__playwright__binding__controller__'].some(key => key in window);
                window.initialized = 'beforeSite' in window;
            </script>""")
            return
        if self.path.startswith("/attachment"):
            self.reply(
                "THIS MUST NEVER BE REQUESTED", content_type="application/octet-stream"
            )
            return
        if self.path == "/away":
            self.reply("<script>location.href='/attachment/navigation';</script>")
            return
        if self.path == "/frame":
            self.reply('<iframe id="child" src="http://localhost:18081/page"></iframe>')
            return
        if self.path == "/cross":
            self.send_response(302)
            self.send_header("Location", "http://localhost:18081/page")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/popup":
            action = "window.open('/attachment/popup', '_blank');"
        elif self.path == "/navigation":
            action = "location.href='/away';"
        elif self.path == "/error":
            action = "fetch('/failure', {method:'POST'});"
        else:
            action = """const response = await fetch('/token', {method:'POST'});
                const value = await response.json();
                const a = document.createElement('a');
                a.href = value.url; a.download = 'fixture.apk'; a.click();"""
        self.reply(
            """<html><head><script>window.initObserved = window.beforeSite === true;</script></head>
            <body><button id="download" data-file-id="123">Download</button><button class="duplicate">A</button>
            <button class="duplicate">B</button><script>
            document.querySelector('#download').addEventListener('click', async event => {
                if (!event.isTrusted) throw new Error('Native click required'); ACTION
            });</script>FRAME</body></html>""".replace("ACTION", action).replace(
                "FRAME",
                '<iframe id="scope" src="/bindings"></iframe>'
                if self.path == "/bridge"
                else "",
            )
        )

    def do_POST(self):
        records.append(("POST", self.path))
        if self.path == "/hold":
            held.set()
            release.wait()
        if self.path == "/failure":
            self.reply('{"success":0,"errorCode":-51}', 400, "application/json")
        else:
            self.reply(
                '{"success":1,"url":"/attachment/ajax"}',
                content_type="application/json",
            )
        if self.path == "/disconnect" and signals["disconnect"] is not None:
            signals["disconnect"]()


def api(client, path="/page", **options):
    return client.post("/v1", json={"url": BASE + path, "maxTimeout": 60000, **options})


def assert_no_attachment_transfer():
    assert not any(path.startswith("/attachment") for _, path in records), records
    assert not any(path.startswith("/.byparr/") for _, path in records), records


def verify_frame_isolation(client):
    """Native helpers work under CSP without injecting bridge state into frames."""
    response = api(
        client,
        "/bridge",
        initScript="window.beforeSite = true;",
        script="""async () => {
            if(document.readyState !== 'complete')await new Promise(r=>window.addEventListener('load',r,{once:true}));
            const child=document.querySelector('#scope').contentWindow;
            if(child.polluted !== false || child.initialized !== false)throw new Error('Child frame was instrumented');
            if(await navigator.serviceWorker.register('/worker.js') !== undefined || await child.navigator.serviceWorker.register('/worker.js') !== undefined)throw new Error('Service worker registration was not blocked');
            await byparr.watchRequest('attachment',{method:'GET',urlPrefix:location.origin+'/attachment',abort:true});
            await byparr.finishWith('attachment');await byparr.click('#download');return null;
        }""",
    )
    assert response.status_code == 200, response.text
    assert response.json()["scriptResult"]["value"]["aborted"] is True
    assert_no_attachment_transfer()
    assert not any(path == "/worker.js" for _, path in records), records
    print(
        "PASS private helper routing under CSP and uninjected child frames", flush=True
    )


async def verify_disconnect():
    """Cancel through the actual ASGI event after browser-side activity begins."""
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def notify() -> None:
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "http.disconnect"})

    signals["disconnect"] = notify
    body = json.dumps(
        {
            "url": BASE + "/page",
            "script": "async () => { await fetch('/disconnect',{method:'POST'}); return await new Promise(() => {}); }",
        }
    ).encode()
    await queue.put({"type": "http.request", "body": body})
    sent = []

    async def send(message) -> None:
        sent.append(message)

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
        "server": ("127.0.0.1", 8191),
        "client": ("127.0.0.1", 4321),
    }
    try:
        await app(scope, queue.get, send)
        assert any(message.get("status") == 499 for message in sent), sent
    finally:
        signals["disconnect"] = None


def verify_redirected_helpers(client):
    """Keep native helpers usable after canonicalization or an HTTP redirect."""
    recipe = """async () => {
        await byparr.watchRequest('attachment',{method:'GET',urlPrefix:location.origin+'/attachment',abort:true});
        await byparr.finishWith('attachment'); await byparr.click('#download'); return null;
    }"""
    for url in ("http://LOCALHOST:18081/page", BASE + "/cross"):
        response = api(client, url=url, script=recipe)
        assert response.status_code == 200, response.text
        assert response.json()["scriptResult"]["value"]["aborted"] is True
        assert_no_attachment_transfer()
    print(
        "PASS canonical origin and cross-origin redirect helper availability",
        flush=True,
    )


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 18081), Fixture)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with TestClient(app) as client:
            if "--frame-isolation" in sys.argv:
                verify_frame_isolation(client)
                return
            if "--redirect-scripting" in sys.argv:
                verify_redirected_helpers(client)
                return
            verify_frame_isolation(client)
            response = api(
                client,
                initScript="window.beforeSite = true;",
                script="async args => ({before: window.initObserved, args, cookie: document.cookie})",
                scriptArgs={"fileId": "123", "literal": "LIMIT"},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["scriptResult"]["value"]["before"] is True
            assert body["scriptResult"]["value"]["args"]["literal"] == "LIMIT"
            assert "fixture=browser" not in body["scriptResult"]["value"]["cookie"]
            assert any(cookie["httpOnly"] for cookie in body["solution"]["cookies"])
            assert body["solution"]["response"].startswith("<html")
            assert 'id="download"' in body["solution"]["response"]
            print(
                "PASS initialization ordering, async JSON arguments/output and HttpOnly cookie metadata",
                flush=True,
            )

            token_submissions = records.count(("POST", "/token"))
            recipe = """async args => {
                const button = document.querySelector('#download');
                if (button.dataset.fileId !== args.fileId) throw new Error('Wrong requested build');
                await byparr.watchRequest('attachment', {method:'GET', urlPrefix:args.base+'/attachment', abort:true});
                if (args.response) await byparr.watchResponse('resolution', {method:'POST', url:args.base+'/token'});
                await byparr.finishWith('attachment');
                await byparr.click('#download');
                return await byparr.waitFor('attachment');
            }"""
            for path, suffix in (
                ("/page", "ajax"),
                ("/popup", "popup"),
                ("/navigation", "navigation"),
            ):
                response = api(
                    client,
                    path,
                    script=recipe,
                    scriptArgs={
                        "fileId": "123",
                        "base": BASE,
                        "response": path == "/page",
                    },
                    blockMedia=True,
                )
                assert response.status_code == 200, (path, response.text)
                result = response.json()["scriptResult"]
                assert result["value"]["url"] == BASE + "/attachment/" + suffix, result
                assert (
                    result["value"]["aborted"] is True
                    and "status" not in result["value"]
                ), result
                if path == "/page":
                    assert result["captures"]["resolution"]["status"] == 200, result
                assert_no_attachment_transfer()
                print(
                    "PASS native click, pre-transfer capture and retained result: "
                    + suffix,
                    flush=True,
                )
            assert records.count(("POST", "/token")) - token_submissions == 1, records
            verify_redirected_helpers(client)

            response = api(
                client,
                "/frame",
                script="""async () => {
                await byparr.watchRequest('attachment', {method:'GET',urlPrefix:'http://localhost:18081/attachment',abort:true});
                await byparr.finishWith('attachment'); await byparr.click('#download','#child'); return null;
            }""",
            )
            assert response.status_code == 200, response.text
            assert (
                response.json()["scriptResult"]["value"]["url"]
                == "http://localhost:18081/attachment/ajax"
            )
            assert_no_attachment_transfer()
            print("PASS native input in a cross-origin child frame", flush=True)

            response = api(
                client,
                "/error",
                script="""async args => {
                await byparr.watchResponse('failure', {method:'POST', url:args.base+'/failure'});
                await byparr.click('#download'); return await byparr.waitFor('failure');
            }""",
                scriptArgs={"base": BASE},
            )
            assert response.status_code == 200, response.text
            failure = response.json()["scriptResult"]["value"]
            assert failure["status"] == 400 and failure["body"]["errorCode"] == -51, (
                failure
            )
            print("PASS actual upstream error response preserved", flush=True)

            result = []
            worker = threading.Thread(
                target=lambda: result.append(
                    api(
                        client,
                        script="async () => { await fetch('/hold',{method:'POST'}); return {released:true}; }",
                    )
                )
            )
            worker.start()
            held.wait()
            queued_result = []
            queued_worker = threading.Thread(
                target=lambda: queued_result.append(api(client, script="() => null"))
            )
            queued_worker.start()
            try:
                while client.get("/ready").json()["browser"]["queued"] != 1:
                    pass
                assert not queued_result
            finally:
                release.set()
                worker.join()
                queued_worker.join()
            assert result[0].status_code == 200, result[0].text
            assert queued_result[0].status_code == 200, queued_result[0].text
            print("PASS FIFO scripted admission and cheap readiness", flush=True)

            asyncio.run(verify_disconnect())
            response = api(client, script="() => ({afterDisconnect:true})")
            assert response.status_code == 200, response.text
            print(
                "PASS ASGI client cancellation, cleanup and released browser admission",
                flush=True,
            )

            for index, options in enumerate(
                [
                    {
                        "script": "async () => { throw new Error('secret must not appear'); }"
                    },
                    {
                        "initScript": "throw new Error('private initialization detail');",
                        "script": "() => null",
                    },
                    {
                        "initScript": "this is not valid javascript !",
                        "script": "() => null",
                    },
                    {
                        "script": "async () => { await byparr.click('.duplicate'); return null; }"
                    },
                    {"script": "() => 'x'.repeat(1024 * 1024 + 1)"},
                    {"script": "() => ({value: NaN})"},
                ]
            ):
                response = api(client, **options)
                assert response.status_code in (413, 422), (index, response.text)
                assert "secret must not appear" not in response.text
                assert "private initialization detail" not in response.text
            print(
                "PASS script/init errors, strict native targeting and output bounds",
                flush=True,
            )

            for script in (
                "async () => await new Promise(() => {})",
                "() => { while (true) {} }",
            ):
                response = api(client, script=script, maxTimeout=2000)
                assert response.status_code == 408, response.text
                response = api(client, script="() => ({admission:'released'})")
                assert response.status_code == 200, response.text
                assert (
                    response.json()["scriptResult"]["value"]["admission"] == "released"
                )
            print(
                "PASS host budget and process cleanup for waiting and CPU-bound scripts",
                flush=True,
            )
            response = api(client)
            assert (
                response.status_code == 200 and "scriptResult" not in response.json()
            ), response.text
            print(
                "PASS ordinary GET remains unchanged after scripted requests",
                flush=True,
            )
            assert_no_attachment_transfer()
        metrics = {}
        for name in (
            "memory.peak",
            "memory.events",
            "pids.peak",
            "pids.events",
            "pids.current",
        ):
            file = Path("/sys/fs/cgroup") / name
            if file.exists():
                metrics[name] = file.read_text().strip()
        print("RESOURCE " + json.dumps(metrics), flush=True)
        assert "oom_kill 0" in metrics.get("memory.events", "oom_kill 0"), metrics
        assert metrics.get("pids.events", "max 0") == "max 0", metrics
    finally:
        release.set()
        server.shutdown()
        server.server_close()


BASE = "http://127.0.0.1:18081"
if __name__ == "__main__":
    main()
