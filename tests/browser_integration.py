"""
Sequential real HTTP/browser fixture; run inside the isolated test container.

No files or external requests are created by the fixture. Challenge timing is
controlled by a server event rather than a timer or sleep.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from starlette.testclient import TestClient

from main import app
from src import endpoints

# Standalone protocol fixture: HTTPServer callbacks, concise untyped helpers,
# literal expected statuses and printed evidence keep the wire assertions direct.
# ruff: noqa: D102,D103,ANN002,ANN003,PLR2004,PT018,T201

client = TestClient(app)

records = []
challenge_seen = threading.Event()
challenge_clear = threading.Event()


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, body, status=200, content_type="application/json", headers=None):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/cdn-cgi/challenge-platform/"):
            self.reply("", content_type="application/javascript")
            return
        if self.path == "/clear":
            challenge_clear.wait()
            self.reply(
                "cleared",
                content_type="text/plain",
                headers={"Set-Cookie": "clearance=yes; Path=/"},
            )
            return
        if self.path == "/preflight":
            self.reply(
                "<html>preflight</html>",
                content_type="text/html",
                headers={"Set-Cookie": "preflight=yes; Path=/"},
            )
            return
        self.echo("GET", "")

    def do_POST(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            chunks = []
            while True:
                size = int(self.rfile.readline().split(b";", 1)[0], 16)
                if size == 0:
                    while self.rfile.readline().strip():
                        pass
                    break
                chunks.append(self.rfile.read(size))
                assert self.rfile.read(2) == b"\r\n"
            body = b"".join(chunks).decode()
        else:
            body = self.rfile.read(
                int(self.headers.get("Content-Length", "0"))
            ).decode()
        if self.path.startswith(("/redirect/", "/cross/")):
            code = int(self.path.rsplit("/", 1)[1])
            records.append({"method": "POST", "path": self.path, "body": body})
            location = (
                "http://localhost:18080/echo"
                if self.path.startswith("/cross/")
                else "/echo"
            )
            self.reply("", code, headers={"Location": location})
            return
        if self.path == "/challenge" and "clearance=yes" not in self.headers.get(
            "Cookie", ""
        ):
            records.append({"method": "POST", "path": self.path, "body": body})
            self.reply(
                """<html><head><title>Just a moment...</title></head><body>
                <script src="/cdn-cgi/challenge-platform/fixture.js"></script>
                <div id="challenge-running">Checking your browser</div>
                <script>fetch('/clear').then(()=>location.href='/echo');</script>
                </body></html>""",
                403,
                "text/html",
                {"cf-mitigated": "challenge"},
            )
            challenge_seen.set()
            return
        self.echo("POST", body)

    def echo(self, method, body):
        item = {
            "method": method,
            "path": self.path,
            "body": body,
            "contentType": self.headers.get("Content-Type"),
            "contentLength": self.headers.get("Content-Length"),
            "transferEncoding": self.headers.get("Transfer-Encoding"),
            "cookie": self.headers.get("Cookie", ""),
            "ua": self.headers.get("User-Agent", ""),
        }
        item["authorization"] = self.headers.get("Authorization")
        records.append(item)
        status = (
            int(self.path.rsplit("/", 1)[1])
            if self.path.startswith("/status/")
            else 200
        )
        self.reply(json.dumps(item, ensure_ascii=False), status)


def request(payload):
    response = client.post("/v1", json=payload)
    return response.status_code, response.json()


def case(path, *, cmd="request.post", **kwargs):
    return request(
        {
            "cmd": cmd,
            "url": "http://127.0.0.1:18080" + path,
            "maxTimeout": 60000,
            **kwargs,
        }
    )


def challenge_case(replay):
    challenge_seen.clear()
    challenge_clear.clear()
    original_solver = endpoints.solve_challenge

    async def release_fixture(page, timer) -> None:
        assert challenge_seen.is_set()
        challenge_clear.set()
        await original_solver(page, timer)

    endpoints.solve_challenge = release_fixture
    try:
        return case("/challenge", postData="action=once", replayPostOnChallenge=replay)
    finally:
        endpoints.solve_challenge = original_solver
        challenge_clear.set()


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 18080), Fixture)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        status, result = case("/echo", postData="name=Jos%C3%A9&literal=a%26b%3Dc")
        assert status == 200, result
        item = json.loads(result["solution"]["response"])
        assert (
            item["method"] == "POST"
            and item["body"] == "name=Jos%C3%A9&literal=a%26b%3Dc"
        ), item
        assert item["contentType"] == "application/x-www-form-urlencoded", item
        assert result["solution"]["userAgent"] == item["ua"]
        print("PASS browser form POST and user-agent", flush=True)

        status, result = case(
            "/echo",
            postData='{"name":"José"}',
            headers={"Content-Type": "application/json"},
            preflightUrl="http://127.0.0.1:18080/preflight",
        )
        item = json.loads(result["solution"]["response"])
        assert (
            status == 200
            and item["method"] == "POST"
            and item["body"] == '{"name":"José"}'
        ), result
        assert (
            item["contentType"] == "application/json"
            and "preflight=yes" in item["cookie"]
        ), item
        print("PASS browser JSON POST and same-context preflight cookie", flush=True)

        for code in [303, 307, 308]:
            status, result = case(f"/redirect/{code}", postData="a=b")
            item = json.loads(result["solution"]["response"])
            assert status == 200 and item["method"] == (
                "GET" if code == 303 else "POST"
            ), result
            assert item["body"] == ("" if code == 303 else "a=b"), item
            print(f"PASS browser redirect {code}", flush=True)
        for code in [422, 503]:
            status, result = case(f"/status/{code}", postData="a=b")
            assert status == 200 and result["solution"]["status"] == code, result
            assert json.loads(result["solution"]["response"])["method"] == "POST", (
                result
            )
            print(f"PASS target status {code}", flush=True)
        status, result = case("/echo", cmd="request.get")
        assert (
            status == 200
            and json.loads(result["solution"]["response"])["method"] == "GET"
        ), result
        print("PASS browser GET regression", flush=True)
        for replay in [False, True]:
            before = len(
                [
                    r
                    for r in records
                    if r["path"] == "/challenge" and r["method"] == "POST"
                ]
            )
            status, result = challenge_case(replay)
            after = len(
                [
                    r
                    for r in records
                    if r["path"] == "/challenge" and r["method"] == "POST"
                ]
            )
            assert status == (200 if replay else 409), result
            assert after - before == (2 if replay else 1), records
            if replay:
                assert json.loads(result["solution"]["response"])["method"] == "POST", (
                    result
                )
                assert result["solution"]["status"] == 200, result
            print(f"PASS real-browser controlled challenge replay={replay}", flush=True)
        print(
            json.dumps({"fixtureRequests": len(records), "status": "passed"}),
            flush=True,
        )
    finally:
        for name in ["memory.events", "memory.peak", "pids.events", "pids.peak"]:
            path = Path("/sys/fs/cgroup") / name
            if path.exists():
                print("RESOURCE", name, path.read_text().strip(), flush=True)
        challenge_clear.set()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
