# Transactional browser admission

Authorized 2026-10-04: all requests wait their turn; no opt-in admission flag.
This specification supersedes the earlier immediate busy-429 contract in the
POST and scripting specifications. Browser scripting/Cloudflare compatibility
investigation is separate; this change addresses confirmed consumer contention.
The subsequent `queue-feedback-spec.md` adds live per-request feedback and
documents the current deployment; qualification below records the FIFO release.

## Requirements

- Q1: Default FIFO admission for all browser operations, including ordinary
  GET/POST and scripting. Only the admitted operation may construct a browser.
  A crawler's next request cannot overtake an already waiting interactive request.
- Q2: A queued client's actual ASGI disconnect, or cancellation of its task,
  removes that operation without browser creation or upstream submission. A
  cancellation coinciding with handoff must not strand the slot or skip others.
- Q3: Hold admission throughout browser startup, operation and cleanup, including
  InvisiblePlaywright's exit. On failure/cancellation, close resources before
  handing off. No replay, repeated click, additional browser or persistent session.
- Q4: Bound pending operations to 16 by default (server setting
  `BROWSER_QUEUE_LIMIT`, 1-64). A full backlog returns HTTP 503 before submission;
  an occupied browser alone no longer returns 429. Browser-free `/ready` retains
  its status/version and adds active/queued/queueLimit counts without private data.
- Q5: Queue waiting is event-driven with no invented deadline, polling or sleep.
  Existing `maxTimeout` execution semantics are retained: waiting is outside the
  execution budget, which starts after browser allocation. Client HTTP deadlines
  can disconnect queued requests. Do not claim a whole-request hard deadline.
- Q6: Verify the actual deployed API with concurrent requests, FIFO upstream
  arrival, cancelled queued request with zero submissions, responsiveness of
  readiness while held, and reuse after release/failure. Preserve original 8191
  endpoint, existing runtime, one CPU/2 GiB/512 PIDs and container protections.
- Q7: Deliver source/config/docs and update the existing upstream reminder.
  Remove task-owned staging/test containers and superseded task images after
  verification; recovery rebuilds committed source. Preserve required evidence.

## Stages

| Stage | Status | Criteria |
| --- | --- | --- |
| T1 Admission contracts | COMPLETE | Q1-Q5: focused FIFO/no overtaking, disconnect/task cancellation including handoff, full-queue 503, launch failure/cancelled setup, driver-exit ordering and existing POST/script contracts pass |
| T2 Real browser and original endpoint | COMPLETE | Q1-Q6: installed-runtime FIFO, real queued disconnect with zero submissions, 16-waiter overload, GET/scripted POST and native capture fixtures pass; original HTTPS held POST followed by queued scripted GET both return 200 once each; Prowlarr proxy test 200; limits/security/network preserved |
| T3 Reconciliation and delivery | COMPLETE | Q7: source/configuration/docs committed and pushed in cd07c46; reminder inspected; final runtime-source/production verification and reviewed local/server cleanup pass |

All stages are COMPLETE. The earlier zero-byte cache markers have been removed
using freshly reviewed cleanup tickets. The scripting and promotion ledgers now
record their resolved cleanup criteria. Blockers: none. Tracked deferrals: none.

T1 verification: the initial FIFO regression failed against the busy-429 code;
the updated focused admission/POST/script contract checks and affected lint,
format and whitespace checks pass. No browser executes concurrently in those
controlled lifecycle tests. Installed-browser behavior was subsequently verified
in T2.

T2 verification: image
`sha256:38f540160714261a43a82a094c47440d9a4f02c24aed0b3967d150e0c3b758de`
reuses the unchanged installed browser/dependencies. Candidate fixture peak:
1039261696 bytes / 240 PIDs, no OOM/PID-limit events. Production after original
HTTPS qualification and actual unchanged Prowlarr testing: healthy, restart count
0, peak 1233649664 bytes / 251 PIDs, no OOM/PID-limit events. A test-harness module
path error before browser tests restored production automatically; correcting
the launcher allowed fresh installed-runtime verification to pass. Production
was briefly stopped for isolated testing to avoid overlapping browsers.

## Client contract

No request flag is needed. Every operation that uses a browser joins the same
FIFO. HTTP 503 means the pending bound was reached and that operation was never
queued or submitted; HTTP 429 is no longer used for ordinary browser contention.
An HTTP connection abandoned while waiting is removed before browser creation.
Once admitted, existing GET/POST and scripting behavior applies unchanged.

`GET /ready` requires no browser and returns, for example:

```json
{"status":"ok","version":"custom-post-scripting-queue","browser":{"active":true,"queued":2,"queueLimit":16}}
```

`active` includes browser startup and cleanup. Queue waiting does not consume
`maxTimeout`. There is no queue deadline or automatic replay; callers should size
their HTTP connection budgets for time spent waiting as well as execution. Run
one application worker because admission ownership is local to its process.

## Recovery

The production Compose file pins the qualified image and records its source
digest. Recovery rebuilds the desired committed source using `Dockerfile.custom`
and the recorded immutable runtime image, then replaces only Byparr using the
existing Compose project and resource/security/network settings. There is no
retained superseded image for rollback. Browser or dependency changes need fresh
qualification of the Firefox upload patch, POST redirects, scripts and admission.

## Final reconciliation

| Requirement | Evidence |
| --- | --- |
| Q1 | Controlled ownership/no-overtaking regression and installed HTTP FIFO arrival, followed by concurrent qualification on the original HTTPS endpoint |
| Q2 | Task cancellation and ASGI disconnect including handoff races; actual HTTP disconnect removed waiting requests with zero upstream submissions |
| Q3 | Driver-exit ordering, failure/cancelled startup regression and reuse after drain; no extra browser or action replay |
| Q4 | Real 16-waiter bound and pre-submission 503, with browser-free readiness responsive while the owner was held |
| Q5 | Ownership futures and actual disconnect events; execution budget begins after browser allocation, with no queue deadline |
| Q6 | Original endpoint and Prowlarr proxy test pass; runtime module hashes match reviewed source; production Compose, limits/security/network and Tailscale configuration preserved |
| Q7 | Documentation/configuration reconciled and existing Monday 09:00 Europe/Berlin reminder updated; reviewed staging/test-container/superseded-image cleanup verified; source commit cd07c46 verified on origin/custom-post |

Server cleanup removed 28 reviewed staging files (110950 bytes), their empty
directories and the unused superseded scripting image. The test container was
removed before cutover. Compact evidence remains intentionally at
`/opt/byparr/admission-evidence.json`. Production was healthy with zero restarts
after cleanup, and the original readiness endpoint returned 200. Independent
host-wide memory/swap pressure delayed operator commands; no unrelated workload
was stopped or modified.

The original HTTPS endpoint also passed a focused actual Unicode JSON POST
probe with its preflight cookie, actual target 503 and exactly one submission.
This verifies the retained POST contract separately from queue ownership.

Local reviewed cleanup transaction `1cba411dcdd7ceb50462e1a81f2cf919` removed the
expendable environment and operator scripts (265158291 logical bytes), with no
exclusions, errors or residuals. The earlier empty-marker cleanup is recorded in
the scripting and promotion specifications. No required work is deferred.
