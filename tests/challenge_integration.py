"""Real browser navigation and detector/solver/replay contract on a controlled fixture."""

import json
import threading
from http.server import ThreadingHTTPServer

from browser_integration import Fixture, challenge_case, records

# Standalone fixture prints evidence and compares explicit wire-status literals.
# ruff: noqa: PLR2004,T201

server = ThreadingHTTPServer(("127.0.0.1", 18080), Fixture)
server.daemon_threads = True
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    for replay in [False, True]:
        before = len(
            [r for r in records if r["path"] == "/challenge" and r["method"] == "POST"]
        )
        status, result = challenge_case(replay)
        after = len(
            [r for r in records if r["path"] == "/challenge" and r["method"] == "POST"]
        )
        assert status == (200 if replay else 409), result
        assert after - before == (2 if replay else 1), records
        if replay:
            assert json.loads(result["solution"]["response"])["method"] == "POST", (
                result
            )
            assert result["solution"]["status"] == 200, result
        print(f"PASS real-browser controlled challenge replay={replay}", flush=True)
finally:
    server.shutdown()
    server.server_close()
