"""Real deployed HTTP FIFO admission, cancellation and browser-regression proof."""

import http.client
import json
import os
import socket
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

from browser_integration import Fixture

# Standalone protocol proof: literal statuses, controlled loopback targets and
# monitored readiness transitions; no sleeps, repeated submissions or site secrets.
# ruff: noqa: N802,D102,D103,S310,PLR2004,PT018,T201,PLR0915

held = threading.Event()
release = threading.Event()
arrivals = []
ENDPOINT = os.environ.get("BYPARR_TEST_ENDPOINT", "http://127.0.0.1:8191")
TARGET = "http://127.0.0.1:18080"


class HeldFixture(Fixture):
    def do_GET(self):
        arrivals.append(("GET", self.path))
        super().do_GET()

    def do_POST(self):
        arrivals.append(("POST", self.path))
        if self.path == "/hold":
            held.set()
            release.wait()
        super().do_POST()


def api(payload):
    request = urllib.request.Request(
        ENDPOINT + "/v1",
        json.dumps(payload).encode(),
        {"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def ready():
    with urllib.request.urlopen(ENDPOINT + "/ready") as response:
        assert response.status == 200
        return json.load(response)


def observe_queue(count):
    # Diagnostic monitoring waits for actual queue membership. It neither
    # expires/cancels the requests nor guesses completion from elapsed time.
    while True:
        state = ready()
        if state["browser"]["queued"] == count:
            return state


def pending_connection(path):
    address = urlsplit(ENDPOINT)
    connection_type = (
        http.client.HTTPSConnection
        if address.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(address.hostname, address.port)
    connection.request(
        "POST",
        "/v1",
        json.dumps({"url": TARGET + path}),
        {"Content-Type": "application/json"},
    )
    return connection


def disconnect(connection):
    connection.sock.shutdown(socket.SHUT_RDWR)
    connection.close()


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 18080), HeldFixture)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threads, connections, results = [], [], {}

    def start(name, payload) -> None:
        def run() -> None:
            results[name] = api(payload)

        thread = threading.Thread(target=run)
        threads.append(thread)
        thread.start()

    try:
        state = ready()
        assert state["browser"]["queueLimit"] == 16
        status, body = api(
            {
                "cmd": "request.post",
                "url": TARGET + "/status/503",
                "postData": '{"value":"José"}',
                "headers": {"Content-Type": "application/json"},
                "preflightUrl": TARGET + "/preflight",
            }
        )
        assert status == 200 and body["solution"]["status"] == 503, body
        echoed = json.loads(body["solution"]["response"])
        assert echoed["method"] == "POST" and echoed["body"] == '{"value":"José"}'
        assert "preflight=yes" in echoed["cookie"]
        print("PASS real API JSON POST/preflight cookies/actual target 503", flush=True)

        start(
            "owner",
            {
                "cmd": "request.post",
                "url": TARGET + "/hold",
                "postData": "once=yes",
                "maxTimeout": 120000,
            },
        )
        held.wait()
        start("get", {"url": TARGET + "/queued/get"})
        observe_queue(1)
        start(
            "scriptPost",
            {
                "cmd": "request.post",
                "url": TARGET + "/queued/post",
                "postData": "second=yes",
                "script": "() => ({transaction:'scriptPost'})",
            },
        )
        observe_queue(2)
        cancelled = pending_connection("/cancelled")
        observe_queue(3)
        disconnect(cancelled)
        observe_queue(2)
        assert ("GET", "/cancelled") not in arrivals
        print("PASS actual queued disconnect; zero upstream submission", flush=True)

        for index in range(14):
            connections.append(pending_connection(f"/cancelled/full/{index}"))
            observe_queue(3 + index)
        status, body = api({"url": TARGET + "/must-not-submit"})
        assert status == 503 and "queue full" in body["detail"].lower(), body
        assert ready()["browser"]["active"] is True
        for connection in connections:
            disconnect(connection)
        connections.clear()
        observe_queue(2)
        print(
            "PASS bounded 16-waiter backlog, full-queue 503 and responsive readiness",
            flush=True,
        )

        release.set()
        for thread in threads:
            thread.join()
        assert set(results) == {"owner", "get", "scriptPost"}, results
        assert all(status == 200 for status, _ in results.values()), results
        assert results["scriptPost"][1]["scriptResult"]["value"] == {
            "transaction": "scriptPost"
        }
        sequence = [
            (method, path)
            for method, path in arrivals
            if path in {"/hold", "/queued/get", "/queued/post"}
        ]
        assert sequence == [
            ("POST", "/hold"),
            ("GET", "/queued/get"),
            ("POST", "/queued/post"),
        ], sequence
        assert not any(
            path.startswith("/cancelled") or path == "/must-not-submit"
            for _, path in arrivals
        ), arrivals
        print(
            "PASS FIFO ordinary GET and scripted POST, once each after prior browser cleanup",
            flush=True,
        )
        status, body = api({"url": TARGET + "/after-queue"})
        assert status == 200 and "scriptResult" not in body
        final = observe_queue(0)
        assert final["browser"]["active"] is False, final
        print("PASS ordinary GET after queue drain; idle admission", flush=True)
    finally:
        for connection in connections:
            disconnect(connection)
        release.set()
        for thread in threads:
            thread.join()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
