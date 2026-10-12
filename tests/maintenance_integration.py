"""Verify URL-scoped cookies using the installed browser and real HTTP."""

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.endpoints import read_item
from src.models import LinkRequest
from src.utils import get_browser

# Standalone controlled HTTP fixture, consistent with the existing wire proofs.
# ruff: noqa: ANN002,PLR2004,T201


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        """Keep request noise out of qualification output."""

    def do_GET(self):
        """Serve the requested cookie origin without external requests."""
        body = b"<html><body>maintenance fixture</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


async def verify():
    """Keep the clearance cookie and exclude a third-party cookie."""
    async for dep in get_browser():
        await dep.context.add_cookies(
            [
                {
                    "name": "clearance",
                    "value": "kept",
                    "url": "http://127.0.0.1:18083/",
                },
                {
                    "name": "advert",
                    "value": "excluded",
                    "url": "https://unrelated.test/",
                },
            ]
        )
        result = await read_item(LinkRequest(url="http://127.0.0.1:18083/"), dep)
        assert result.solution.status == 200
        assert "maintenance fixture" in result.solution.response
        assert {cookie["name"] for cookie in result.solution.cookies} == {"clearance"}
    print(
        "PASS installed browser HTTP navigation and URL-scoped clearance cookies",
        flush=True,
    )


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 18083), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        asyncio.run(verify())
    finally:
        server.shutdown()
        server.server_close()
