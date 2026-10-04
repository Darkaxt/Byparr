"""Actual HTTP feedback while one real browser holds transactional admission."""

import http.client
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import api_integration as fixture

# Standalone protocol fixture: controlled loopback, explicit statuses and events.
# ruff: noqa: S310,T201,PLR2004,PT017,PT018,PLR0915


def feedback(request_id):
    """Read current counts without requesting another browser operation."""
    try:
        with urllib.request.urlopen(fixture.ENDPOINT + "/queue/" + request_id) as r:
            assert r.headers["Cache-Control"] == "no-store"
            return r.status, json.load(r)
    except urllib.error.HTTPError as error:
        assert error.headers["Cache-Control"] == "no-store"
        return error.code, json.load(error)


def observe(request_id, position=None):
    """Monitor the real membership transition without sleeps or cancellation."""
    while True:
        status, result = feedback(request_id)
        if status == 200 and (
            result["position"] == position
            if position is not None
            else result["state"] == "queued"
        ):
            return result


def submit(request_id, path):
    """Open a real waiting HTTP request, with identity known before submission."""
    address = urlsplit(fixture.ENDPOINT)
    kind = (
        http.client.HTTPSConnection
        if address.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = kind(address.hostname, address.port)
    connection.request(
        "POST",
        "/v1",
        json.dumps(
            {
                "url": fixture.TARGET + path,
                "requestId": request_id,
                "script": "() => ({feedback:true})",
            }
        ),
        {"Content-Type": "application/json"},
    )
    return connection


def main(*, shared=False):
    """Verify live movement, duplicate rejection, cancellation and final identity."""
    owner_id, first_id, second_id = (str(uuid4()) for _ in range(3))
    server = ThreadingHTTPServer(("127.0.0.1", 18080), fixture.HeldFixture)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results, connections = [], []
    owner = threading.Thread(
        target=lambda: results.append(
            fixture.api(
                {
                    "cmd": "request.post",
                    "url": fixture.TARGET + "/hold",
                    "postData": "once=yes",
                    "maxTimeout": 120000,
                    "requestId": owner_id,
                }
            )
        )
    )
    try:
        owner.start()
        fixture.held.wait()
        assert feedback(owner_id)[1]["state"] == "active"
        first = submit(first_id, "/cancelled-feedback")
        connections.append(first)
        first_position = observe(first_id)["position"]
        second = submit(second_id, "/feedback-second")
        connections.append(second)
        before = observe(second_id)
        assert before["position"] > first_position
        if not shared:
            assert before == {
                "requestId": second_id,
                "state": "queued",
                "position": 2,
                "total": 2,
                "queueLimit": 16,
            }
        assert feedback(first_id)[1]["position"] == first_position
        status, _ = fixture.api(
            {"url": fixture.TARGET + "/duplicate", "requestId": second_id}
        )
        assert status == 409
        assert feedback(second_id)[1]["position"] == before["position"]
        fixture.disconnect(first)
        connections.remove(first)
        while feedback(first_id)[0] != 404:
            pass
        after = feedback(second_id)[1]
        assert after["position"] < before["position"]
        if not shared:
            assert after["position"] == after["total"] == 1
        assert fixture.arrivals == [("POST", "/hold")], fixture.arrivals
        print(
            "PASS live feedback movement, queued disconnect, duplicate 409 and no extra submission",
            flush=True,
        )
        fixture.release.set()
        owner.join()
        response = second.getresponse()
        body = json.load(response)
        assert response.status == 200 and body["requestId"] == second_id
        assert response.headers["X-Request-ID"] == second_id
        assert body["scriptResult"]["value"] == {"feedback": True}
        second.close()
        connections.remove(second)
        assert results[0][0] == 200 and results[0][1]["requestId"] == owner_id
        assert feedback(owner_id)[0] == feedback(second_id)[0] == 404
        assert fixture.arrivals == [("POST", "/hold"), ("GET", "/feedback-second")], (
            fixture.arrivals
        )
        status, body = fixture.api({"url": fixture.TARGET + "/legacy-feedback"})
        assert status == 200 and str(UUID(body["requestId"])) == body["requestId"]
        assert feedback(body["requestId"])[0] == 404
        print(
            "PASS original request results/headers, FIFO once each, automatic legacy ID and no retained history",
            flush=True,
        )
    finally:
        for connection in connections:
            fixture.disconnect(connection)
        fixture.release.set()
        if owner.ident is not None:
            owner.join()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
