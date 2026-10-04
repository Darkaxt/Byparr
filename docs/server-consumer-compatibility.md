# Server consumer compatibility assessment

Authorized 2026-10-04: monitor the transactional admission delivery, assess
existing server consumers, and patch confirmed integration incompatibilities.
The admission specification remains authoritative for Byparr itself. This task
does not modify its runtime or the independently owned Telefonillo/Morphe clients.

## Acceptance criteria

- S1: Confirm the delivered source and actual production version/image, original
  localhost/Docker/Tailscale 8191 endpoints, privacy and resource limits.
- S2: Discover active MiniPC consumers from configuration, inspect the queue and
  client deadline contract, and run the existing Prowlarr proxy test without
  changing saved configuration or repeating an upstream POST/browser action.
- S3: Correct the generic weekly maintenance script's incompatible registry pull
  of the locally built Byparr pin. Leave all other service update calls intact.
  Check Byparr with browser-free `/ready` and require HTTP 200, not a root redirect
  or 404. Preserve the cron schedule and existing backup/locking behavior.
- S4: Verify focused regressions and shell syntax, deploy only the maintenance
  script safely, and verify its content, service identity and real readiness.
  Record results, commit the reviewed artifacts and pause the completed follow-up.

## Stages

| Stage | Status | Criteria | Evidence |
| --- | --- | --- | --- |
| Consumer and deployment assessment | COMPLETE | S1-S2 | Source cd07c46/cd64cd1 and server admission evidence reviewed; live version custom-post-scripting-queue, qualified image and limits confirmed; saved Prowlarr host unchanged, timeout 120 s; live proxy test HTTP 200 in 5.04 s |
| Maintenance integration and delivery | COMPLETE | S3-S4 | Focused regressions failed against original script and pass against patch; Linux bash syntax passes; exact two-edit deployment guarded by original hash and existing updater lock; deployed checksum matches source; cron and container identities unchanged; live readiness 200 while busy |

Blockers: none. Tracked deferrals: none.

## Findings

Production uses image
`sha256:38f540160714261a43a82a094c47440d9a4f02c24aed0b3967d150e0c3b758de`.
Live Docker inspection confirms one CPU, 2 GiB memory, 512 PIDs, localhost-only
8191 publication, `/ready` health monitoring, no OOM and zero restarts.
The original HTTPS `/ready` returns 200 with queueLimit 16 and active/queued counts.

The queue contains at most 16 waiting operations plus one active browser. FIFO
ownership spans startup and cleanup; cancellation/disconnection drops queued
operations before submission. A full queue returns 503, replacing contention
429. Responses otherwise retain the GET/POST/scripting contracts. Queue waiting
does not consume maxTimeout; the client's connection budget still can expire.
It is not a guaranteed whole-request execution deadline. High sustained backlog
can therefore outlast existing caller budgets; no speculative timeout increase
or automatic replay is applied.

Prowlarr is the active server browser consumer discovered in CT120. Its saved
FlareSolverr proxy remains `http://byparr:8191/` with requestTimeout 120 seconds.
The authenticated live proxy test returned 200 in 5.04 seconds with the original
configuration. This test did not encounter queue waiting; the implementing task's
installed-runtime and original-endpoint concurrency evidence establishes FIFO and
cancellation separately. Compose/environment and Bindery settings inspection
found no other Byparr browser consumer in CT120. CT100 has no Docker/runtime
consumer. Lidarr and other users of Prowlarr are indirect consumers.

The active Saturday updater `/usr/local/sbin/update-minipc-leftover-services.sh`
unconditionally calls `docker compose pull` for Byparr. The current Compose pin
is a local image ID, not a published registry repository reference. Pulling an
image requires a repository name/tag or repository@digest; see the
[Docker reference](https://docs.docker.com/reference/cli/docker/image/pull/).
With `set -e`, that incompatible step can prevent later service updates.
The custom runtime must continue to be updated through its reviewed source/build
workflow, not the generic registry updater. The cron remains Saturday 05:45.

The maintenance probe currently accepts redirects and even 404 at `/`. It does
not launch a browser, but it is weaker than the existing production readiness
contract. Replacing only this probe with `/ready` and HTTP 200 avoids treating a
missing route as healthy and leaves the browser queue untouched.

## Focused maintenance patch

The tracked operator script in `tools/update_minipc_leftover_services.sh` mirrors
the deployed script with only the two Byparr maintenance changes. Its original
SHA-256 was `839768155ee1dded89285e4709569a3e7549a0a26bae0bf15eaad505bac69d11`.
Deployment must check that source hash and acquire the existing updater lock
before replacement. Do not execute the full updater as a verification step:
that would unnecessarily update/recreate unrelated services.

## Verification and reconciliation

- S1: Actual image and version match the delivered queue runtime; localhost,
  Docker-network and tailnet 8191 endpoints retain their previous configuration.
  One browser, one CPU, 2 GiB and 512 PIDs remain unchanged.
- S2: Prowlarr's saved proxy test returned 200 without configuration changes.
  Existing caller budgets remain unchanged; no observed integration failure
  justified increasing them. FIFO does not guarantee completion within a caller
  deadline under a large backlog. Telefonillo/Morphe adaptation remains with
  their existing owners; this assessment introduced no duplicate client edits.
- S3: Generic registry updates no longer pull or recreate the reviewed local
  Byparr image. Other compose_update calls, backup behavior and cron are identical
  to the original script. The Byparr HTTP probe now requires `/ready` status 200.
- S4: Regression checks demonstrate both original defects and pass after the
  patch. Actual Linux `bash -n` passes. Deployment held the existing updater
  flock, checked the original hash, rejected any edits beyond the reviewed two
  replacements, atomically installed the script preserving ownership/mode, and
  checked container IDs/start times/restart counts and the cron checksum before
  and after. Deployed script SHA-256 is
  `7f5ac454c0790154964dab7e196a2e5b4a108f090e5e96bf5eafc89d82860a06`.
  Real readiness returned 200 while active=true, queued=0: monitoring did not
  acquire the browser. The atomic staging file was removed; no local temporary
  environment, caches or validation containers were created for this assessment.

All required criteria are verified. No service was restarted, no upstream
POST/action was replayed, and no resource cap or client timeout was increased.
The reviewed operator script, focused tests and this ledger are committed for
repeatable maintenance. The one-time compatibility follow-up is paused after
delivery; the separate weekly upstream reminder remains unchanged.
