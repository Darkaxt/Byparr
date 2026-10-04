"""CT120-only guarded deployment; preserves all state and rolls back on failure."""

import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

BASE = "sha256:f2b26429893d4c4cb71941b7ee50b1bdecd9d5f9f9e02d5410615e9f4f7c8d95"
CORE_HASH = "465b2e8807168ed6b46dd769ddf3865f82555403aebebe45bc21509a5843e405"
UPDATER_HASH = "7f5ac454c0790154964dab7e196a2e5b4a108f090e5e96bf5eafc89d82860a06"


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def inspect(name):
    return json.loads(command("docker", "inspect", name))[0]


def atomic(path, contents):
    stat = path.stat()
    staging = path.with_name(path.name + ".queue-wait-staging")
    try:
        with staging.open("x") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staging, stat.st_mode)
        os.chown(staging, stat.st_uid, stat.st_gid)
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


def main():
    lock = open("/var/lock/update-minipc-leftover-services.lock", "a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    compose = Path("/opt/prowlarr/compose.yaml")
    updater = Path("/usr/local/sbin/update-minipc-leftover-services.sh")
    original_compose, original_updater = compose.read_text(), updater.read_text()
    assert hashlib.sha256(updater.read_bytes()).hexdigest() == UPDATER_HASH
    assert inspect("prowlarr")["Image"] == BASE
    image = json.loads(command("docker", "image", "inspect", "homelab/prowlarr:2.6.5.5623-queue-wait"))[0]
    assert image["Config"]["Labels"]["eu.remaxku.prowlarr.queue-wait"] == "1"
    assert hashlib.sha256(Path("/opt/prowlarr/queue-build/Prowlarr.Core.dll").read_bytes()).hexdigest() == CORE_HASH
    byparr_id = inspect("byparr")["Id"]
    key = ET.fromstring(command("docker", "exec", "prowlarr", "cat", "/config/config.xml")).findtext("ApiKey")

    def api(route, data=None, method=None, timeout=None):
        request = urllib.request.Request("http://127.0.0.1:9696/api/v1/" + route,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"X-Api-Key": key, "Content-Type": "application/json"}, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response)

    _, commands = api("command", timeout=20)
    assert not any(c.get("status") in ("started", "queued") for c in commands), "Do not interrupt indexing work"
    _, proxies = api("indexerproxy", timeout=20)
    target = next(p for p in proxies if any(f["name"] == "host" and f.get("value") == "http://byparr:8191/" for f in p["fields"]))
    assert next(f["value"] for f in target["fields"] if f["name"] == "requestTimeout") == 120
    candidate = copy.deepcopy(target)
    candidate["fields"].append({"name": "waitForQueue", "value": True})
    old_line = "    image: lscr.io/linuxserver/prowlarr:latest\n"
    assert original_compose.count(old_line) == 1
    updated_compose = original_compose.replace(old_line, f"    image: {image['Id']}\n    pull_policy: never\n")
    old_call = "compose_update prowlarr /opt/prowlarr prowlarr"
    assert original_updater.count(old_call) == 1
    updated_updater = original_updater.replace(old_call,
        '# Prowlarr carries the qualified queue-wait client patch; do not replace it with stock.\n'
        'log "Skipping registry update for queue-aware Prowlarr; retaining qualified image"')

    def recreate():
        print(command("docker", "compose", "-f", str(compose), "up", "-d", "--no-deps", "--pull", "never", "prowlarr"), flush=True)
        while True:
            assert inspect("prowlarr")["State"]["Running"], "Prowlarr exited during startup"
            try:
                return api("system/status", timeout=5)
            except (urllib.error.URLError, ConnectionError):
                continue

    configuration_saved = False
    try:
        atomic(compose, updated_compose)
        recreate()
        api(f"indexerproxy/{target['id']}", candidate, "PUT")
        configuration_saved = True
        _, saved = api("indexerproxy", timeout=20)
        actual = next(p for p in saved if p["id"] == target["id"])
        values = {f["name"]: f.get("value") for f in actual["fields"]}
        assert values["waitForQueue"] is True and values["requestTimeout"] == 120
        assert values["host"] == "http://byparr:8191/"
        for p in proxies:
            if p["id"] != target["id"]:
                assert p == next(q for q in saved if q["id"] == p["id"])
        atomic(updater, updated_updater)
        command("bash", "-n", str(updater))
        assert inspect("byparr")["Id"] == byparr_id
        assert inspect("prowlarr")["Image"] == image["Id"]
        print(json.dumps({"image": image["Id"], "coreSha256": CORE_HASH,
                          "waitForQueue": True, "requestTimeout": 120,
                          "updaterSha256": hashlib.sha256(updater.read_bytes()).hexdigest()}), flush=True)
    except BaseException:
        if configuration_saved:
            api(f"indexerproxy/{target['id']}", target, "PUT")
        atomic(compose, original_compose)
        atomic(updater, original_updater)
        recreate()
        raise
    finally:
        lock.close()


if __name__ == "__main__":
    main()
