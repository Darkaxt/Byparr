"""Actual browser proof: background CF scripts do not prolong an interstitial."""

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.challenge import challenge_present, solve_challenge
from src.endpoints import read_item
from src.models import LinkRequest
from src.utils import TimeoutTimer, get_browser

# Standalone wire fixture follows the existing integration-test conventions.
# ruff: noqa: ANN002, D102, PLR2004, T201

release = threading.Event()


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/release":
            release.wait()
            body = b"ready"
        elif self.path.startswith("/cdn-cgi/"):
            body = b""
        elif self.path == "/challenge":
            body = b"""<script src="/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1"></script>
            <div id="challenge-running">Checking your browser</div>
            <script>fetch('/release').then(() => location.href='/app');</script>"""
        else:
            body = b"""<html><title>Actual target page</title>
            <script src="/cdn-cgi/challenge-platform/scripts/precursor/main.js"></script>
            <script src="/cdn-cgi/challenge-platform/h/b/scripts/jsd/main.js"></script>
            <body>requested build and download button</body></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


async def verify():
    """Prove initial classification, genuine detection and real clearance."""
    async for dep in get_browser():
        await dep.page.goto("http://127.0.0.1:18084/app")
        assert not await challenge_present(dep.page)
        print(
            "PASS actual target with precursor and jsd scripts is not an interstitial",
            flush=True,
        )
        await dep.page.goto("http://127.0.0.1:18084/challenge")
        assert await challenge_present(dep.page)
        release.set()
        await solve_challenge(dep.page, TimeoutTimer(duration=5))
        assert dep.page.url.endswith("/app")
        assert not await challenge_present(dep.page)
        print(
            "PASS genuine interstitial clears into target retaining CF background scripts",
            flush=True,
        )
        # The complete API endpoint also returns the successful target body.
        result = await read_item(
            LinkRequest(url="http://127.0.0.1:18084/app", maxTimeout=5000), dep
        )
        assert result.solution.status == 200
        assert "requested build and download button" in result.solution.response
        print("PASS endpoint returns target 200 and requested HTML", flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 18084), Fixture)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        asyncio.run(verify())
    finally:
        release.set()
        server.shutdown()
        server.server_close()
