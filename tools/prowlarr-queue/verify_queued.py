"""Run inside CT120; test Prowlarr's real solver request against the live FIFO.

Saved proxy configuration is never changed. The scaled test uses a 10-second
execution budget, so its stock HTTP deadline is 15 seconds. The diagnostic
observation boundary does not cancel or release the underlying request.
"""

import concurrent.futures
import copy
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse


def http(url, data=None, key=None, timeout=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Api-Key"] = key
    request = urllib.request.Request(
        url, data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def api_key(container):
    config = subprocess.check_output(
        ["docker", "exec", container, "cat", "/config/config.xml"], text=True
    )
    return ET.fromstring(config).findtext("ApiKey")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", default="prowlarr-queue-qualification")
    parser.add_argument("--port", type=int, default=19696)
    parser.add_argument("--only-queue", action="store_true")
    args = parser.parse_args()
    client_key = api_key(args.container)
    _, proxies = http("http://127.0.0.1:9696/api/v1/indexerproxy", key=api_key("prowlarr"), timeout=20)
    proxy = next(p for p in proxies if any(
        f.get("name") == "host" and f.get("value") == "http://byparr:8191/"
        for f in p["fields"]
    ))
    _, ready = http("http://127.0.0.1:8191/ready", timeout=5)
    assert not ready["browser"]["active"] and ready["browser"]["queued"] == 0, "Do not contend with existing work"
    held, release = threading.Event(), threading.Event()

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            body = b"<html><body>queue qualification</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            assert self.path == "/hold"
            held.set()
            release.wait()
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

    fixture = ThreadingHTTPServer(("172.21.0.1", 0), Fixture)
    server_thread = threading.Thread(target=fixture.serve_forever, daemon=True)
    server_thread.start()
    fixture_url = f"http://172.21.0.1:{fixture.server_port}/"
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as workers:
            for queue_aware in ([True] if args.only_queue else [False, True]):
                held.clear()
                release.clear()
                owner_id = str(uuid.uuid4())
                owner = workers.submit(http, "http://127.0.0.1:8191/v1", {
                    "requestId": owner_id, "url": fixture_url, "maxTimeout": 120000,
                    "script": "async () => { await fetch('/hold', {method:'POST'}); return {released:true}; }",
                })
                assert held.wait(30), "Diagnostic: browser did not reach fixture"
                candidate = copy.deepcopy(proxy)
                for field in candidate["fields"]:
                    if field["name"] == "requestTimeout":
                        field["value"] = 10
                candidate["fields"] = [f for f in candidate["fields"] if f["name"] != "waitForQueue"]
                candidate["fields"].append({"name": "waitForQueue", "value": queue_aware})
                started = time.monotonic()
                tested = workers.submit(http, f"http://127.0.0.1:{args.port}/api/v1/indexerproxy/test", candidate, client_key)
                try:
                    # Poll actual FIFO state; no delay decides ownership.
                    observed = False
                    while not tested.done() and time.monotonic() - started < 20:
                        _, state = http("http://127.0.0.1:8191/ready", timeout=5)
                        if state["browser"]["queued"] > 0:
                            observed = True
                            break
                    assert observed, "Actual client request did not enter FIFO"
                    if queue_aware:
                        finished = threading.Event()
                        tested.add_done_callback(lambda _: finished.set())
                        # This diagnostic timer observes the external old HTTP deadline.
                        assert not finished.wait(16), "Client still expires while waiting"
                        assert not tested.done()
                        release.set()
                        status, result = tested.result()
                        assert status == 200, (status, result)
                    else:
                        status, result = tested.result()
                        assert status == 400, (status, result)
                        assert time.monotonic() - started >= 15
                        release.set()
                    assert owner.result()[0] == 200
                    print(json.dumps({"queueAware": queue_aware, "status": status,
                                      "elapsedSeconds": round(time.monotonic() - started, 2),
                                      "executionBudgetSeconds": 10, "oldHttpDeadlineSeconds": 15}), flush=True)
                finally:
                    release.set()
    finally:
        release.set()
        fixture.shutdown()
        fixture.server_close()
        server_thread.join()
    _, saved = http("http://127.0.0.1:9696/api/v1/indexerproxy", key=api_key("prowlarr"), timeout=20)
    assert saved == proxies, "Diagnostic unexpectedly changed saved proxy configuration"


if __name__ == "__main__":
    main()
