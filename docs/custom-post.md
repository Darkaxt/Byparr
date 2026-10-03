# Custom POST fork runbook

Fork: https://github.com/Darkaxt/Byparr, branch `custom-post`.
Upstream: https://github.com/ThePhaseless/Byparr, `main` at
`8bcc5e89c4e3378fb9559b2899b9d285fa1b69db` for this implementation.

Production was promoted to this fork on 2026-10-03, on the original port 8191.
See [production deployment, evidence and rollback](production-promotion.md).
The isolated-deployment section below records the original development service,
which remains stopped on 8192; its historical production-preservation statements
describe that earlier validation task.

## API behavior

POST `/v1` is the API transport. The `cmd` now selects real browser-network GET
or POST navigation. Each operation uses a fresh browser context; there are no
persistent sessions or automatic client retries.

```json
{
  "cmd": "request.post",
  "url": "https://target.example/search",
  "postData": "query=hello%20world",
  "maxTimeout": 60000
}
```

`postData` is an exact UTF-8 string, limited to 1 MiB. Form content type is the
default; callers perform their own form encoding. For JSON, send a JSON string
in `postData` and `headers: {"Content-Type": "application/json"}`. Headers are
limited to 32 entries/16 KiB; browser-owned Cookie, Host, Content-Length,
User-Agent, connection, sec-* and proxy-* headers cannot be overridden.

An optional `preflightUrl` performs GET clearance on the same HTTP(S) origin
before the POST in the same browser context. Cookies, browser user agent and
egress therefore stay together. Preflight and POST share the API's `maxTimeout`
budget, which retains the existing seconds/milliseconds compatibility.

When a submitted POST encounters a challenge, it is never silently resubmitted.
After clearance, the API returns HTTP 409. Only explicit
`replayPostOnChallenge: true` permits one additional POST after clearance. Use
that option only for an operation where replay is acceptable. A second challenge
returns 409 without a third submission. A clearance timeout returns 408.

Redirects retain browser HTTP semantics: 303 changes POST to GET, while 307/308
retain its body. Cross-origin redirects strip Authorization; method changes
drop body-specific headers. JSON/plain responses retain raw response text; HTML
is the settled DOM. `solution.status` is the actual final target status, including
4xx/5xx. Inspect both the API HTTP/status result and `solution.status`.

`GET /ready` checks API readiness without a browser or external traffic. Browser
operations share one admission slot; excess operations return immediate HTTP
429 and are never queued or submitted. Cleanup finishes before a successful
response is sent. Run exactly one application worker; the limit is per process.
The inherited `/health` launches a browser and is unsuitable for idle monitoring.

## Isolated deployment

The test service lives at `/opt/byparr-custom` in the media LXC. It has a separate
Compose project, container and network, with `127.0.0.1:8192` mapped to its API.
The existing production instance, consumers, Compose file and Tailscale Serve
configuration are unchanged. No public endpoint or production switchover exists.

The test service is deliberately **stopped after verification**. Inside the LXC:

```sh
docker compose -f /opt/byparr-custom/compose.custom.yaml start
curl http://127.0.0.1:8192/ready
# After manual testing:
docker compose -f /opt/byparr-custom/compose.custom.yaml stop
```

From Proxmox, prepend `pct exec 120 --` to those commands.

Limits: 0.5 CPU, 1 GiB memory including bounded tmpfs, no additional swap,
256 PIDs, logs limited to 2 x 5 MiB. The container runs as UID 1000, with a
read-only root filesystem, dropped capabilities and no privilege escalation.
Writable caches/profiles are private bounded tmpfs and disappear when stopped.
There is no restart loop or browser-launching Docker health check.

`Dockerfile.custom` reuses an already-installed immutable upstream image,
avoiding browser/dependency downloads during the build. Its small overlay
contains this fork and a Firefox Juggler upload-stream correction. Exact source
anchors fail a build if an engine update needs review. The browser source keeps
its MPL-2.0 header. Do not remove this patch: a plain Playwright navigation
override loses the upload body on 307/308 with the verified bundled engine.

This verified deployment uses upstream image digest
`sha256:874f719518f617d03a60e03411fc5d090647e1a877041e81f8dc965927c7deb6`,
Invisible Playwright 0.7.2 and Firefox `20_151.0_20260817150018`.
The normal Dockerfile also applies the patch, but a full fresh dependency/browser
build and other runtime versions have not been verified in this task.

## Verification and updates

See [verification evidence](custom-post-verification.md) and the
[authoritative specification](custom-post-spec.md). A real external httpbin POST
passed. Live Cloudflare clearance at 1337x timed out and is unverified; the wider
sequence reached the hard memory/PID limits once, while production stayed
unchanged. Fresh controlled tests passed without those events. A specific site's
POST challenge compatibility needs a harmless payload and its own live check.

Operator transfer tools use the existing SSH/LXC route, configured on Windows:

```powershell
$env:BYPARR_PROXMOX_HOST = '<existing Proxmox SSH hostname or address>'
$env:BYPARR_CT_ID = '120'
python tools/stage_remote.py
python tools/deploy_remote.py
```

Stage only while the test service is stopped. Deployment uses `--network=none`
and `--pull=false`; it will not fetch a different runtime image. The tools do not
change authentication, production services or Tailscale. Preserve the private
baseline/evidence files; take a fresh reviewed baseline for a new maintenance run.

Tests are sequential. `tests/api_integration.py` verifies the deployed HTTP API;
the other `*integration.py` scripts verify real browser navigation with a
controlled loopback fixture. The fixture is a deterministic interstitial, not a
live Cloudflare Turnstile service. `tools/validate_remote.py` supports disposable
fixture runs; do not run it concurrently with another browser test.

For upstream propagation: fetch `upstream`, review the delta from the recorded
base, integrate into `custom-post`, and preserve POST validation, one-replay
permission, target status/body semantics, browser cleanup and admission. Review
any browser/dependency change against the redirect patch. Repeat the focused
offline tests and bounded server fixture/API checks, compare production state,
stop the test service, clean exact task-owned artifacts, then commit and push.
Inherited GitHub Actions are disabled to avoid automatic nightly builds or
publishing. The weekly reminder is a review reminder; it does not merge, deploy
or publish changes automatically.
