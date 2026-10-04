# Production promotion specification

User authorization: review Darkaxt/Byparr and, if suitable, replace production
Byparr in CT120. This follow-up explicitly supersedes the earlier task's
production-isolation restriction for the production cutover only.

## Acceptance criteria

- P1: Review source changes, provenance, exact deployed image/source equivalence,
  and browser GET/POST, redirect, challenge/replay and lifecycle contracts.
- P2: Qualify the candidate through real browser fixtures and the HTTP API;
  test existing Prowlarr GET usage. State any live-site coverage limits accurately.
- P3: Preserve container/service name byparr, localhost 8191, existing Docker
  network, DNS resolvers and Tailscale Serve endpoint. Use an immutable reviewed
  image, restart unless-stopped, one browser, one CPU, 2 GiB memory without extra
  swap, 512 PIDs, non-root/read-only security and bounded ephemeral storage/logs.
  Use /ready for Docker monitoring instead of launching browsers through /health.
- P4: Persist production Compose, retain the original pinned runtime and exact
  configuration with a documented rollback command. Verify Prowlarr proxy test,
  tailnet access, actual POST, health, resource bounds and process cleanup after
  cutover. Leave the separate development container stopped.
- P5: Record evidence and limitations, reconcile all criteria, commit/push the
  reviewed deployment artifacts, and remove only expendable task artifacts.

The 2 GiB/512 PID production budget provides headroom above measured test peaks
of 914 MiB/240 PIDs and the prior bounded OOM. Concurrency remains one browser;
the API returns 429 for overlapping browser operations. Site-specific challenge
clearance is not guaranteed and requires actual target evidence.

## Stages

| Stage | Status | Criteria | Evidence |
| --- | --- | --- | --- |
| Review and qualification | COMPLETE | P1-P2 | Reviewed source matches candidate image AST; real HTTP API/browser fixtures pass, including GET/form/JSON/status/cookies/replay/redirects; Prowlarr candidate proxy test 200; original and candidate live 1337x GET both return target 200 |
| Production cutover and verification | COMPLETE | P3-P4 | Original port/name/network/DNS/Serve preserved; production Prowlarr proxy test 200; real JSON POST from Windows over Tailscale to httpbin returned target 200 and exact payload; healthy with no restarts/OOM/PID events; original pinned Compose/image retained for rollback; development container stopped |
| Reconciliation and delivery | COMPLETE | P5 | Reviewed deployment artifacts committed/pushed; verification recorded; validation environment removed; former empty-cache restriction resolved through reviewed cleanup on 2026-10-04 |

The former external P5 cleanup blocker was resolved on 2026-10-04. The cleanup
helper had misclassified UV's empty `.git` marker as a repository, and command
policy rejected its removal. Updated reviewed cleanup verified generated
provenance and empty-marker identities before removing the two zero-byte files
and empty parents. The obsolete partial ticket was revoked. Blockers: none.
Tracked deferrals: none.

## Reviewed outcome (2026-10-03)

No blocking source defects were found in the reviewed POST changes. All runtime
Python modules in the deployed image match the reviewed Git source AST. Focused
offline tests validate API models, replay, response handling and lifecycle. Real
browser and deployed candidate API checks exercise the actual browser/runtime,
including form/JSON bodies, GET, 303/307/308, cross-origin credential stripping,
cookies, 422/503, controlled challenge replay, admission and cleanup.

The pinned deployed image is
`sha256:6bf4d2a0cb2397e99972d468aed830a3736bbc3f70cd90c8cf811e3b721ce9d5`,
tagged `local/byparr-post:prod-756127f`. It reuses the recorded upstream browser
runtime; no runtime dependencies or browser version were upgraded in promotion.
The offline locked environment uses different dependency revisions, so actual
runtime fixture checks, rather than offline tests alone, establish compatibility.

Both the original and candidate retrieved `https://1337x.to/home/` with API and
target status 200 (8.25 s and 12.61 s respectively). This proves live GET access
on this occasion, not universal Cloudflare clearance or real-site challenged POST.
Controlled challenge/replay and real external POST remain distinct evidence.

After cutover, the existing Prowlarr proxy test returned 200 without changing
its `http://byparr:8191/` configuration or restarting Prowlarr. A real JSON POST
from Windows through Tailscale to `https://httpbin.org/post` returned API ok,
target 200 and the exact JSON probe. Docker readiness is healthy and Tailscale
Serve configuration is unchanged. Production resource checks recorded a peak
of 983392256 bytes (~938 MiB), 254 PIDs, zero restarts and zero memory/PID events.
The earlier 1 GiB test limit would have left little headroom for this workload.

An attempted production fixture call received the documented 429 because the
existing Paginas Amarillas crawler held the browser slot. Its real GETs continued
to return 200. Final diagnostic requests were started at actual completion events;
no client was paused and no timed retries or server queuing were introduced.
That historical immediate-429 admission behavior was superseded on 2026-10-04
by `transactional-admission-spec.md`: all consumers now wait in a bounded FIFO.
Production readiness
uses /ready; /health remains a browser operation and can occupy the same slot.

The isolated development deployment helper previously required the original
upstream image in its baseline. It now verifies the reviewed baseline against
actual Byparr/Prowlarr container identities, images, start times and restart
counts instead. This permits the new production image while rejecting a stale
pre-promotion baseline before any build or deployment. Archive historical
evidence and capture/review a fresh baseline before the next development run.

## Final reconciliation

P1-P4 are satisfied and verified against the reviewed source, deployed runtime,
real browser fixtures, existing Prowlarr integration and Tailscale HTTPS endpoint.
Deployment artifacts were committed and pushed in `1e0ace6`. P5 evidence and
delivery are satisfied. The former empty-cache cleanup blocker was resolved on
2026-10-04 by reviewed transaction `b3837759c401a82f28a9f1157e6f7063`; the two
zero-byte markers and empty parent directories are gone.
Transactional cleanup deleted 420963179 logical bytes of task-owned validation
files, including the disposable environment and linked cache names, without
removing unrelated files or the shared link targets. No residual markers remain.
No reboot, global Docker restart or Prowlarr restart was performed.

## Production endpoints and recovery

- Local CT120 API: `http://127.0.0.1:8191/v1`.
- Shared Docker network API: `http://byparr:8191/v1`.
- Tailnet API: `https://media-apps-minipc.tail94fa2c.ts.net:8191/v1`.
- Tailnet readiness: `https://media-apps-minipc.tail94fa2c.ts.net:8191/ready`.
- Proxmox SSH: `root@100.74.127.101`; prepend `pct exec 120 --` to CT commands.
- Active Compose: `/opt/byparr/compose.yaml`; portable configuration is
  `compose.production.yaml` in this repository.
- Compact private cutover evidence: `/opt/byparr/promotion-evidence.json`.
- The historical development container `byparr-custom` was removed during scripting cleanup.

The original cutover retained an image and Compose snapshot for rollback. The
user subsequently required source-based recovery and removal of superseded
custom images, the development container and temporary rollback configuration.
That original rollback procedure is no longer applicable.

This is the historical POST promotion record. Current deployment/admission and
source-based recovery are documented in `transactional-admission-spec.md`; no
permanent superseded custom image is retained.
