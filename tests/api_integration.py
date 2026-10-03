"""Exercise the separately deployed HTTP API and deterministic overload handling."""

import json
import queue
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from browser_integration import Fixture

# Standalone protocol fixture: literal statuses, HTTPServer method names and
# printed evidence are intentional. urllib targets are fixed loopback HTTP URLs.
# ruff: noqa: N802,D102,D103,S310,PLR2004,PT018,T201

held = queue.Queue()
release = threading.Event()


class HeldFixture(Fixture):
    def do_POST(self):
        if self.path == "/hold":
            held.put("request-arrived")
            release.wait()
        super().do_POST()


def api(payload):
    request = urllib.request.Request(
        "http://127.0.0.1:8191/v1",
        json.dumps(payload).encode(),
        {"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


server = ThreadingHTTPServer(("127.0.0.1", 18080), HeldFixture)
server.daemon_threads = True
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with urllib.request.urlopen("http://127.0.0.1:8191/ready") as response:
        assert response.status == 200
    status, body = api(
        {
            "cmd": "request.post",
            "url": "http://127.0.0.1:18080/status/503",
            "postData": '{"value":"José"}',
            "headers": {"Content-Type": "application/json"},
            "preflightUrl": "http://127.0.0.1:18080/preflight",
        }
    )
    assert status == 200 and body["solution"]["status"] == 503, body
    echoed = json.loads(body["solution"]["response"])
    assert echoed["method"] == "POST" and echoed["body"] == '{"value":"José"}', echoed
    assert "preflight=yes" in echoed["cookie"], echoed
    print("PASS deployed HTTP API JSON POST, cookie and actual 503 status", flush=True)
    result = []

    def call_held():
        try:
            result.append(
                api(
                    {
                        "cmd": "request.post",
                        "url": "http://127.0.0.1:18080/hold",
                        "postData": "once=yes",
                    }
                )
            )
        finally:
            held.put("request-finished")

    thread = threading.Thread(target=call_held)
    thread.start()
    assert held.get() == "request-arrived", result
    status, body = api(
        {
            "cmd": "request.post",
            "url": "http://127.0.0.1:18080/echo",
            "postData": "should=reject",
        }
    )
    assert status == 429, body
    with urllib.request.urlopen("http://127.0.0.1:8191/ready") as response:
        assert response.status == 200
    release.set()
    thread.join()
    assert result[0][0] == 200, result
    status, body = api({"cmd": "request.get", "url": "http://127.0.0.1:18080/echo"})
    assert (
        status == 200 and json.loads(body["solution"]["response"])["method"] == "GET"
    ), body
    print(
        "PASS deployed busy 429, cheap readiness and released browser admission",
        flush=True,
    )
finally:
    release.set()
    server.shutdown()
    server.server_close()
