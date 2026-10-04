# Live per-request queue feedback

Authorized: caller feedback must report the current position while its original
browser request waits, rather than a snapshot returned after completion. Existing
default FIFO admission remains authoritative in `transactional-admission-spec.md`.

## Acceptance criteria

- F1: `/v1` accepts an optional UUID `requestId`, generates one when absent,
  returns it in successful JSON and the `X-Request-ID` response header. Callers
  supply their UUID before submitting when they need feedback while waiting.
  Duplicate live IDs return 409 without submitting another browser operation.
  Invalid IDs are rejected by existing request validation before admission.
- F2: `GET /queue/{requestId}` returns live `state`, `position`, `total` and
  `queueLimit`, plus the same ID. Position is one-based among pending requests;
  total counts pending requests, excluding the owner. Active requests have
  position 0. Feedback uses no browser and is marked `Cache-Control: no-store`.
  Disconnect/cancellation/handoff immediately change the next feedback response.
- F3: Completed, cancelled, rejected and unknown requests are not retained:
  feedback returns 404 when the ID is not tracked. No result history, timers,
  retry/resubmission, browser concurrency or resource-budget changes. IDs expose
  counts/state only, with no URL, cookies or private browser output.
- F4: Focused regressions demonstrate moving positions, duplicate rejection,
  cancellation/removal and identity in ordinary/scripted responses. Verify actual
  HTTP feedback while a real browser is held and after cancellation/handoff on
  the original endpoint; verify Prowlarr and existing caps. Deliver docs/source,
  reviewed cleanup and commit/push. Existing deployment authorization applies.

## Stages

| Stage | Status | Acceptance |
| --- | --- | --- |
| F1 Contract and implementation | COMPLETE | F1-F3: focused feedback movement, duplicate rejection, removal, browser-free/uncached endpoint, identity in ordinary/scripted responses and existing POST/script/admission regressions pass; affected lint passes |
| F2 Original-endpoint qualification and delivery | COMPLETE | F4 installed-runtime and original HTTPS live feedback pass; Prowlarr/caps/configuration/source/cleanup verified; commit 9136423 pushed and inspected on origin/custom-post |

All stages are COMPLETE. Blockers: none. Tracked deferrals: none.

## Verification and reconciliation

| Criterion | Evidence |
| --- | --- |
| F1 | New regressions failed before implementation; supplied/generated identity in ordinary/scripted JSON and headers passes; installed HTTP duplicate-ID 409 has zero extra submission |
| F2 | Installed HTTP feedback moves from 2/2 to 1/1 after an earlier waiter disconnects; feedback remains browser-free while an actual browser is held; original HTTPS feedback movement also passes alongside normal consumers; no-store inspected |
| F3 | Actual cancelled/finished IDs return 404, no cancelled upstream arrival, no retained identities; ordinary GET/scripted POST/FIFO/full-queue 503 and readiness regressions pass |
| F4 | Original HTTPS qualification and actual Prowlarr proxy test 200 pass; Prowlarr identity/start/config and Tailscale configuration unchanged; reviewed runtime module hashes match deployed source, production Compose matches repository configuration; cleanup verified; source commit 9136423 verified on origin/custom-post |

Deployed image:
`sha256:7da2c6b4295b1ac51bc5dca500ce9d5b800bf65d44c0b7e9bdfd700033314e51`.
Version: `custom-post-scripting-queue-feedback`.
Runtime/browser dependencies and Firefox patches are unchanged. Installed fixture
peak: 958267392 bytes / 241 PIDs, zero OOM/PID-limit events, no browser after
qualification. Original production endpoint remained healthy with zero restarts
after cleanup; final readiness reported idle admission. The existing one CPU,
2 GiB without additional swap, 512 PIDs and security/network settings are intact.
Production was briefly stopped during isolated qualification to avoid overlapping
browsers. An operator source-label guard initially prevented cutover because its
pattern was malformed; correcting the literal replacement preceded deployment.

Reviewed cleanup removed the candidate test container, 26 staging files
(120522 bytes), empty staging directories and the superseded FIFO image.
Compact required evidence remains at `/opt/byparr/queue-feedback-evidence.json`.
Recovery rebuilds the desired committed source against the immutable base in
`Dockerfile.custom`; no unused custom rollback image is retained.
The existing weekly upstream reminder now also preserves request identity and
live feedback behavior. No new automation or notification schedule was created.

Local cleanup transaction `d3f6caf9f942a04b2b844c89968452f9` removed the expendable
environment/operator scripts (265154481 logical bytes), with no exclusions,
errors or residuals. Required runbook/specification/evidence outputs are preserved.
