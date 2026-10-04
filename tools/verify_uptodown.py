"""One fresh original-endpoint resolution followed by native original-APK GET."""

import hashlib
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

# Standalone, sequential operator proof. No tokens, cookies or signed URLs are
# printed; the private response is retained under the gitignored evidence path.
# ruff: noqa: INP001,T201,S310,PLR2004,PT018

ENDPOINT = "https://media-apps-minipc.tail94fa2c.ts.net:8191"
PAGE = "https://showly-2-0.en.uptodown.com/android/download/1220892131-x"
FILE_ID = "1220892131"
EXPECTED_HASH = "f0fac7fc5474168ca982fd220361f3bbb76d4f4f3ed9e89cf03d2465d2b77074"
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "local-evidence/browser-scripting"
APK = Path("D:/Temp/byparr-browser-scripting/showly-3.72.0.apk")


class AttachmentRedirect(urllib.request.HTTPRedirectHandler):
    """Keep this verification on the documented Uptodown attachment hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0917 - framework callback signature
        """Reject redirects outside the attachment's declared HTTPS hosts."""
        target = urlsplit(newurl)
        if target.scheme != "https" or target.hostname not in {
            "dw.uptodown.com",
            "dw.uptodown.net",
        }:
            message = "Attachment redirect left the documented HTTPS hosts"
            raise ValueError(message)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def cookie_jar(cookies: list[dict]) -> http.cookiejar.CookieJar:
    """Reuse browser cookies only on their declared domain/path/secure scope."""
    jar = http.cookiejar.CookieJar()
    for value in cookies:
        domain = value["domain"]
        expiry = value.get("expires", -1)
        jar.set_cookie(
            http.cookiejar.Cookie(
                version=0,
                name=value["name"],
                value=value["value"],
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=domain.startswith("."),
                domain_initial_dot=domain.startswith("."),
                path=value["path"],
                path_specified=True,
                secure=value.get("secure", False),
                expires=int(expiry) if expiry > 0 else None,
                discard=expiry <= 0,
                comment=None,
                comment_url=None,
                rest={"HttpOnly": value.get("httpOnly", False)},
                rfc2109=False,
            )
        )
    return jar


def main() -> int:
    """Run once; rejected flows are evidence, never automatic retries."""
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(ENDPOINT + "/ready") as response:
        ready = json.load(response)
    assert ready["version"] in {
        "custom-post-scripting",
        "custom-post-scripting-queue",
        "custom-post-scripting-queue-feedback",
    }, ready
    payload = {
        "cmd": "request.get",
        "url": PAGE,
        "maxTimeout": 120000,
        "blockMedia": False,
        "script": (ROOT / "examples/uptodown.js").read_text(),
        "scriptArgs": {"fileId": FILE_ID},
    }
    request = urllib.request.Request(
        ENDPOINT + "/v1",
        json.dumps(payload).encode(),
        {"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            status, result = response.status, json.load(response)
    except urllib.error.HTTPError as error:
        status, result = error.code, json.load(error)
    (EVIDENCE / "uptodown-response.json").write_text(
        json.dumps({"apiStatus": status, "result": result}, indent=2)
    )
    print("Original endpoint API status", status, flush=True)
    if status != 200:
        print(
            "Resolution not verified; private failure evidence retained; no retry or native download",
            flush=True,
        )
        return 2
    return verify_attachment(result)


def verify_attachment(result: dict) -> int:
    """Verify a freshly captured response and its original native attachment."""
    capture = result["scriptResult"]["value"]
    assert (
        capture["kind"] == "request"
        and capture["method"] == "GET"
        and capture["aborted"] is True
    )
    target = urlsplit(capture["url"])
    assert (
        target.scheme == "https"
        and target.hostname == "dw.uptodown.com"
        and target.path.startswith("/dwn/")
    )
    resolution = result["scriptResult"]["captures"]["resolution"]
    assert resolution["status"] == 200 and resolution["body"]["success"] == 1
    assert resolution["url"].endswith(f"/file/{FILE_ID}/download-url")
    assert (
        capture["url"]
        == "https://dw.uptodown.com/dwn/" + resolution["body"]["data"]["downloadURL"]
    )
    user_agent = result["solution"]["userAgent"]
    assert user_agent and capture["requestHeaders"]["user-agent"] == user_agent
    headers = {"User-Agent": user_agent}
    for name in ("accept", "referer"):
        if name in capture["requestHeaders"]:
            headers[name] = capture["requestHeaders"][name]
    opener = urllib.request.build_opener(
        AttachmentRedirect(),
        urllib.request.HTTPCookieProcessor(cookie_jar(result["solution"]["cookies"])),
    )
    APK.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    with (
        opener.open(
            urllib.request.Request(capture["url"], headers=headers)
        ) as response,
        APK.open("wb") as output,
    ):
        native_status = response.status
        content_type = response.headers.get("content-type", "")
        final_host = urlsplit(response.url).hostname
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            total += len(chunk)
            output.write(chunk)
    assert native_status == 200 and final_host in {"dw.uptodown.com", "dw.uptodown.net"}
    assert zipfile.is_zipfile(APK), "Attachment is not a ZIP-format APK"
    with zipfile.ZipFile(APK) as archive:
        names = set(archive.namelist())
        assert "AndroidManifest.xml" in names and "classes.dex" in names
    actual_hash = digest.hexdigest()
    assert actual_hash == EXPECTED_HASH, (
        "Original file differs from independent handoff bytes; inspect identity before accepting"
    )
    proof = {
        "page": PAGE,
        "fileId": FILE_ID,
        "resolutionStatus": resolution["status"],
        "capturedBeforeTransfer": capture["aborted"],
        "nativeStatus": native_status,
        "nativeContentType": content_type,
        "finalHost": final_host,
        "bytes": total,
        "sha256": actual_hash,
        "format": "APK",
        "matchesIndependentHeliumBytes": True,
    }
    (EVIDENCE / "uptodown-verification.json").write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
