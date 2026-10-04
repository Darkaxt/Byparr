# Browser scripting API

Optional fields on the existing private `POST /v1` interface:

| Field | Behavior |
| --- | --- |
| `initScript` | JavaScript body installed before website scripts in the requested page's main document on the original requested origin; repeated on navigation within that origin |
| `script` | JavaScript function expression evaluated after DOMContentLoaded and any interstitial handling; its asynchronous return is awaited |
| `scriptArgs` | JSON argument passed to that function |

Initialization does not run in child frames or popups. Native helpers remain
available in the requested page after normal redirects. Await any asynchronous
work started by initialization from the main `script`; initialization itself
does not pause website loading. Scripts execute in the page with browser
permissions, not in Python or a userscript-extension environment.

Helpers use a native request-owned binding confined to the main document;
they do not install Playwright binding globals in child/challenge frames or send
helper arguments to the website. The bundled adapter honors explicitly requested
CSP bypass in the scripted main document, leaving challenge-frame policies intact.
Scripted contexts block service-worker registration through Playwright’s supported
context option to keep interception authoritative. The installed Firefox requires
its worker subsystem enabled for request interception; its native preference is
left unchanged. This worker policy applies to all frames. Ordinary
GET/POST contexts retain their previous settings. `initScript` provides a
per-request compatibility patch without an extension or persistent installation.

Script requests use the existing `maxTimeout` seconds/milliseconds convention.
That budget covers navigation, initialization, helpers and the awaited result.
The host enforces it even for an unresolved promise or a CPU-bound page script.
All callers now wait in a bounded FIFO before browser allocation, without an
opt-in flag. Queue waiting does not consume this execution budget; clients must
allow for waiting in their own HTTP budgets. A queued disconnect removes the
request before submission. Client disconnect cancels the scripted operation. There are no automatic action retries,
POST replays or persistent browser sessions. Existing navigation-level
`replayPostOnChallenge` permission remains unchanged.

## Browser helpers

The main document receives `window.byparr`:

- `await byparr.click(selector, frameSelector = null)` uses strict Playwright
  native input/actionability. An optional frame selector targets a child frame.
- `await byparr.watchRequest(name, options)` registers the first matching request.
  Registration completes before this returns. `options` requires `method` plus
  either `url` or `urlPrefix`; `abort: true` captures and blocks the request before
  transfer. Prefixes compare actual origins, not textual hostname prefixes.
- `await byparr.watchResponse(name, options)` registers the first matching response
  and collects its actual HTTP status, headers and bounded JSON/text body.
  Matching does not filter out error status codes. Response capture cannot abort
  a request that has already been submitted.
- `await byparr.waitFor(name)` waits for a previously registered capture.
- `await byparr.finishWith(name)` selects a registered capture as the terminal
  result. Call it before triggering the action. Its host-owned result remains
  available if navigation destroys the page's JavaScript execution context.

Names are unique identifier strings, up to 64 characters. Captures operate at
browser-context scope, including initial popup requests; scripts and helper
calls originate from the requested page's main document. Do not send token POSTs
again from a recipe when the website already submitted them.

Example JavaScript function for an explicitly selected download button:

```javascript
async args => {
    await byparr.watchRequest("download", {
        method: "GET",
        urlPrefix: args.downloadPrefix,
        abort: true
    });
    await byparr.finishWith("download");
    await byparr.click(args.buttonSelector);
    return await byparr.waitFor("download");
}
```

Send that expression as the `script` JSON string, with selector and prefix in
`scriptArgs`. Registration, selection and action order are significant. Waiting
for the request before clicking would deadlock until the API budget expires.

## Output and errors

Ordinary page HTML, navigation URL/status, user agent and relevant scoped cookies
remain under `solution`. Structured results are separate:

```json
{
  "scriptResult": {
    "value": {
      "kind": "request",
      "url": "https://downloads.example/file/key",
      "method": "GET",
      "requestHeaders": {},
      "aborted": true
    },
    "captures": {},
    "terminalCapture": "download"
  }
}
```

The actual `captures` map contains completed named records. With `finishWith`,
`value` is the selected capture record; otherwise it is the function's JSON
return, including explicit `null`. Request interception has no target HTTP
status because the attachment was not fetched. Response capture records have
their actual `status`, response `headers`, `body` and `requestHeaders`.

HTTP 422 reports validation, script or helper failure; completed response evidence
is retained in `detail.scriptResult` when a recipe rejects that response. HTTP
413 reports captured-output/page limits; an oversized JavaScript return reports
a controlled 422. HTTP 408 reports the execution budget; HTTP 503 reports a full
16-waiter backlog before submission. An occupied browser alone queues the request.
Arbitrary script exception
text is not exposed or logged. Captures may contain credentials or signed URLs:
keep responses private and scope cookies to their destinations for native HTTP.

Bounds: 64 KiB UTF-8 per script and serialized arguments, 1 MiB combined structured
output/capture metadata, eight named captures and two pages per operation. A
third page fails the operation; all pages are closed during cleanup. Browser
admission and existing container CPU, memory, PID and ephemeral-storage caps
remain in force.

Controlled fixtures demonstrate the interface, including zero matching attachment
requests reaching their fixture server. They do not establish a particular site's
Turnstile acceptance. Live Uptodown qualification and production state belong in
the [authoritative specification](browser-scripting-spec.md).

## Uptodown recipe and verified deployment

Use [examples/uptodown.js](../examples/uptodown.js) as the `script` string,
`scriptArgs: {"fileId":"1220892131"}`, the exact build URL below, and a positive
`maxTimeout` (the live verification used 120000 milliseconds). Send one request to
`https://media-apps-minipc.tail94fa2c.ts.net:8191/v1`. The recipe requires the page's
actual load event, derives its IDs/options, installs captures before the native
click, and lets the website generate and submit its token. No persistent patch,
extension, saved token or server-side Uptodown special case is needed.

On 2026-10-03 the original endpoint resolved
`https://showly-2-0.en.uptodown.com/android/download/1220892131-x` with API 200 and
website POST 200/success=1. The attachment was intercepted and aborted; a native
HTTP client downloaded 12004991 bytes from Uptodown. SHA-256:
`f0fac7fc5474168ca982fd220361f3bbb76d4f4f3ed9e89cf03d2465d2b77074`.
Android SDK `aapt` independently read package `com.michaldrabik.showly2`,
versionName `3.72.0`, versionCode `843`. These are host-side file checks;
Morphe owns subsequent Android integration/device validation.

The verified immutable server image is
`sha256:3f44719d681077eb91f489c38520f83e50beddc74adcc5515daa897f37833889`.
It retains the installed Firefox/dependency layers and adds the reviewed adapter
patch alongside the existing POST redirect fix. Build through `Dockerfile.custom`;
both patches fail the build if their upstream anchors change. Keep the deployment
private, resource-limited and single-browser as configured in `compose.production.yaml`.

Prowlarr's existing proxy test returned 200 without configuration changes or a
restart. Production peak memory was 1104240640 bytes (about 1.03 GiB), peak PIDs
266, with no restart, OOM or PID-limit events. The service was healthy and its
browser was absent after qualification. These are measured peaks, not reservations.
Readiness uses `/ready` without a browser. The stopped development container was
removed during final cleanup.

The previous implementation is committed as `756127f`. The superseded image,
stopped development container and temporary rollback configuration were removed
after source delivery at the user's request. Recovery rebuilds that source against
the immutable base pinned in
`Dockerfile.custom`. From a checkout containing that commit, use an explicit
temporary build directory:

```sh
mkdir /opt/byparr-recovery-build
git archive 756127f | tar -x -C /opt/byparr-recovery-build
docker build --network none --pull=false -f /opt/byparr-recovery-build/Dockerfile.custom -t local/byparr-post:recovery-756127f /opt/byparr-recovery-build
```

Verify the rebuilt image, then explicitly update only the production image,
VERSION and source label while retaining its existing limits/network/port, and
apply the compose service. Remove the recovery build directory and unused recovery
image after its defined use. No permanent rollback image is required.

`tools/verify_uptodown.py` repeats the
one-request/native-download host check and keeps secrets under gitignored
`local-evidence`; a full-queue 503 means no browser submission occurred. Do not replay the
click or token POST automatically. Controlled fixtures prove interface contracts;
this live run proves Uptodown acceptance on this occasion, not every future
Turnstile decision.

Current admission behavior, deployed image and FIFO verification are recorded in
[transactional admission](transactional-admission-spec.md). The Uptodown image and
verification above describe the original scripting qualification on 2026-10-03.
