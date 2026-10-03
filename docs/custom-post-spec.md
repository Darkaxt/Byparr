# Custom Byparr POST fork: authoritative specification

Authorization: user requested a custom fork and deployment beside the existing
server instance, including testing, with server stability and disk hygiene as
binding constraints. Existing production Byparr and its Prowlarr integration
must remain untouched.

## Requirements and acceptance criteria

- R1: Maintain a GitHub fork at Darkaxt/Byparr, with upstream provenance,
  documented custom behavior, verified changes committed and pushed. No external
  release or scheduled publishing is needed.
- R2: `/v1` accepts `request.get` and `request.post`, rejects unsupported commands,
  and supports exact string `postData` plus caller headers. POST defaults to form
  content type; explicit JSON content type is supported. Body limit is 1 MiB.
  Validation errors are controlled API errors and do not launch browsers.
- R3: POST uses actual browser-network navigation, retains browser cookies,
  user agent and egress, and preserves normal redirect semantics. Interception
  affects only the requested initial main-frame navigation, never challenge
  traffic, frames or subresources. An optional same-origin `preflightUrl` performs
  GET challenge clearance before POST in the same browser context.
- R4: Never silently replay a submitted POST. If it encounters a challenge,
  solve it, then return a controlled 409 explaining resubmission unless the
  caller explicitly sets `replayPostOnChallenge=true`. That permission allows
  exactly one additional submission after clearance; a remaining challenge is
  an error. Ordinary redirects do not authorize extra submissions. Document
  that this option is appropriate only where the caller accepts replay.
- R5: Return the final target's actual HTTP status and headers. HTML is the
  settled DOM; textual JSON/plain responses preserve their response body and
  content type. Preserve GET cookies-only behavior. Do not re-fetch POST content
  using GET. Verify 4xx/5xx and final responses after redirect/challenge.
- R6: At most one browser operation at a time, with immediate 429 for excess
  operations rather than an unbounded queue. Browser cleanup releases admission
  on success, failure and cancellation. A lightweight readiness endpoint must
  not launch a browser. Retain API maxTimeout at the existing protocol boundary.
- R7: Separate test container/project/network and loopback port 8192; no public
  exposure and no production configuration edits. Limit CPU to 0.5 core, memory
  to 1 GiB (including bounded tmpfs), no additional swap, PIDs to 256, logs to
  2 x 5 MiB. Non-root, read-only root filesystem, private bounded writable tmpfs,
  dropped capabilities, no privilege escalation, no automatic restart loop.
  Disable browser-launching Docker health checks. Use the existing immutable
  runtime image where compatible to avoid re-downloading browser/dependencies.
  Test sequentially and do not stress production.
- R8: Before deployment record capacity, original Byparr container identity,
  image, start time and configuration hashes. Verify real browser GET/POST,
  encoding, JSON, redirect behavior, cookies, status, challenge/replay contract,
  admission limits and cleanup with a controlled fixture. Perform a bounded
  real external challenge check. Record clearly any unavailable live challenge
  coverage. Confirm original Byparr/Prowlarr identity and health afterward.
- R9: Attribute generated artifacts before creation; preserve source, deployment
  configuration, deployed image and compact evidence; delete expendable test
  containers, archives, profiles and fixtures. No broad Docker pruning or cleanup
  of pre-existing artifacts. After testing leave the isolated test service
  stopped to avoid ongoing idle resource use, with an explicit start command.
- R10: Once the fork is ready, create a weekly Codex reminder to review and
  propagate upstream changes while preserving custom POST behavior and the
  isolated verification workflow. Default schedule: Mondays at 09:00 Europe/Berlin.

## Explicit scope

No production switchover, persistent sessions, arbitrary browser actions,
upstream PR, scheduled update jobs, releases, proxy/provider changes or unrelated
server repairs. Public fork visibility follows GitHub's upstream public fork
model. Implementation decisions preserving these criteria need no approval.

## Staged execution and reconciliation

| Stage | Status | Requirements | Acceptance evidence |
| --- | --- | --- | --- |
| S1 Browser POST vertical slice | COMPLETE | R2-R5 | Focused regressions pass; CT120 real-browser form/JSON, UTF-8, GET, cookies, 303/307/308 including cross-origin credential stripping, 422/503, controlled challenge rejection and one permitted replay verified |
| S2 Bounded isolated deployment | COMPLETE | R6-R8 | Real deployed API POST/status/cookie, immediate overload 429, readiness and sequential cleanup pass; hard limits inspected; fresh controlled browser workflow zero OOM/PID events, peak 914 MiB/240 PIDs; external httpbin POST passed, external challenge coverage limited as recorded below; production identity/configuration comparison passed |
| S3 Reconcile, document, commit and clean | ACTIVE | R1,R9,R10 and all final criteria | Remaining: final runbook/evidence, reviewed cleanup, stopped service, verified fork commit/push and weekly reminder |

Blockers: none. Tracked deferrals: none. Server preflight established SSH via
Proxmox and `pct exec 120`; direct CT SSH denied public-key
authentication. CT120 has 4 CPUs, 16 GiB RAM, ~13 GiB available and ~540 GiB disk
free. Existing Byparr currently uses appreciable CPU, so tests must remain capped.
Tailscale Serve currently exposes production on HTTPS port 8191; leave it intact.

Resolved implementation detail: the provisional PID limit of 160 was too small
for Firefox threads: real fixture cgroup evidence showed pids.peak=160 and
pids.events max=11, with no memory OOM events and ~705 MiB memory peak. The limit
is adjusted to 256 to support one real browser while retaining a hard cap. All
CPU, memory, concurrency and production-isolation constraints are preserved.

R3 integration decision: real 307 verification exposed a missing upload stream
in the bundled Firefox Juggler observer after a GET navigation is overridden to
POST. The fork carries a narrow build-time observer patch that preserves the
overridden body only across method-preserving 307/308 redirects. Incompatible
browser source anchors fail the build for review. The production browser and
dependency layers are shared read-only, with the observer change in a small
separate image layer.

R8 coverage: a real external form POST to https://httpbin.org/post succeeded,
including UTF-8 form decoding. GET https://1337x.to/home/ detected a Cloudflare
challenge but returned API 408. Across that broader sequence the test container
recorded one bounded browser OOM and PID-limit events; the API recovered and
production remained unchanged. A fresh controlled workflow on the same image
and limits passed with zero memory/PID-limit events (memory.peak=958279680,
pids.peak=240). Real site-specific Cloudflare POST clearance is unverified; the
controlled challenge/replay contract is verified. Do not raise limits or claim
universal challenge clearance to mask this unavailable external coverage.

R6 lifecycle: deployed testing reproduced response delivery before browser
cleanup with FastAPI's default request dependency scope. Browser dependencies
now use function scope, so cleanup and admission release finish before a response
is sent. An ASGI response-order regression and the deployed sequential/overload
workflow verify the correction.
