"""Focused real-browser body/header regression after the Gecko observer fix."""

import json
import threading
from http.server import ThreadingHTTPServer

from browser_integration import Fixture, case

# Standalone fixture prints evidence and compares explicit redirect/status literals.
# ruff: noqa: PLR2004,T201

server = ThreadingHTTPServer(("127.0.0.1", 18080), Fixture)
server.daemon_threads = True
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    for code in [303, 307, 308]:
        status, result = case(
            f"/cross/{code}",
            postData='{"name":"José"}',
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer fixture-secret",
            },
        )
        assert status == 200, result
        item = json.loads(result["solution"]["response"])
        assert item["authorization"] is None, item
        assert item["method"] == ("GET" if code == 303 else "POST"), item
        assert item["body"] == ("" if code == 303 else '{"name":"José"}'), item
        assert item["contentType"] == (None if code == 303 else "application/json"), (
            item
        )
        print(
            f"PASS cross-origin {code}: UTF-8 body, method and credential stripping",
            flush=True,
        )
finally:
    server.shutdown()
    server.server_close()
