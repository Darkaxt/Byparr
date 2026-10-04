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
  An unqueued test alone does not establish compatibility; S5-S6 below provide
  the required deadline separation and actual queued client qualification.
- S3: Correct the generic weekly maintenance script's incompatible registry pull
  of the locally built Byparr pin. Preserve other update calls except the
  queue-aware Prowlarr pin required by S6; that client must not revert to stock.
  Check Byparr with browser-free `/ready` and require HTTP 200, not a root redirect
  or 404. Preserve the cron schedule and existing backup/locking behavior.
- S4: Verify focused regressions and shell syntax, deploy only the maintenance
  script safely, and verify its content, service identity and real readiness.
  Record results, commit the reviewed artifacts and pause the completed follow-up.

## Stages

| Stage | Status | Criteria | Evidence |
| --- | --- | --- | --- |
| Consumer and deployment assessment | COMPLETE | S1-S2 | Current queue-feedback image and original endpoints/caps confirmed; Prowlarr is the direct server consumer; exact client deadline defect reproduced and real queued completion qualified in S5-S6 |
| Maintenance integration and delivery | COMPLETE | S3-S4 | Focused regressions failed against original script and pass against patch; Linux bash syntax passes; exact two-edit deployment guarded by original hash and existing updater lock; deployed checksum matches source; cron and container identities unchanged; live readiness 200 while busy |

## Corrected queue-compatibility scope (2026-10-04)

The earlier overall completion claim is withdrawn. An unqueued proxy test only
proved connectivity; it did not satisfy the original client compatibility
requirement. Prowlarr 2.6.5.5623 sends maxTimeout=120000 and cancels the whole
solver HTTP request after 125 seconds. Queue waiting, startup and cleanup share
the remaining five seconds when execution consumes its full budget.

Additional explicit acceptance criteria for the original authorized integration:

- S5: Separate Prowlarr's Byparr queue wait from its execution allowance. Keep
  maxTimeout=120000, existing endpoints and Byparr resource limits. Do not add
  automatic retries/replays, queue deadlines or changes to unrelated solvers.
- S6: Prove the actual Prowlarr request survives queue waiting beyond its old
  HTTP deadline, then executes once successfully; verify unchanged ordinary
  solver behavior, saved settings, restart persistence and update protection.
  Retain reproducible patch/build/verification artifacts and a defined rollback.

| Correction Stage | Status | Criteria | Evidence |
| --- | --- | --- | --- |
| Prowlarr deadline separation | COMPLETE | S5 | Exact installed upstream commit 12c327808314a7cae1b7301935ee10cabc19609f; stock queue-aware GET/POST regressions fail at 125 s deadline; scoped WaitForQueue patch passes with unchanged maxTimeout=120000 and ordinary 125 s behavior |
| Queued integration and persistent delivery | COMPLETE | S6 | Real stock-mode request fails at 15.8 s; isolated patched request succeeds at 22.41 s and deployed request at 22.01 s after 16 s queue hold; production DB retains flag, host and 120 s budget; immutable image/no-pull Compose and updater guard verified; normal proxy/system tests 200; disposable qualification and temporary build/transfer files removed |

The prior maintenance delivery remains verified. S2 connectivity evidence is
valid but insufficient for queued compatibility. No blockers or deferrals are
currently identified. S5-S6 now satisfy the original missing client compatibility
requirement. Earlier maintenance-specific evidence below remains historical.

## Findings

Current production Byparr uses image
`sha256:7da2c6b4295b1ac51bc5dca500ce9d5b800bf65d44c0b7e9bdfd700033314e51`
and version `custom-post-scripting-queue-feedback`.
Live Docker inspection confirms one CPU, 2 GiB memory, 512 PIDs, localhost-only
8191 publication, `/ready` health monitoring, no OOM and zero restarts.
The original HTTPS `/ready` returns 200 with queueLimit 16 and active/queued counts.

The queue contains at most 16 waiting operations plus one active browser. FIFO
ownership spans startup and cleanup; cancellation/disconnection drops queued
operations before submission. A full queue returns 503, replacing contention
429. Responses otherwise retain the GET/POST/scripting contracts. Queue waiting
does not consume maxTimeout; the client's connection budget still can expire.
It is not a guaranteed whole-request execution deadline. The old Prowlarr
deadline was incompatible with this contract; S5-S6 correct its solver boundary
without increasing execution budgets or adding automatic replay.

Prowlarr is the active server browser consumer discovered in CT120. Its saved
FlareSolverr proxy remains `http://byparr:8191/` with requestTimeout 120 seconds.
The authenticated live proxy test returned 200 in 5.04 seconds with the original
configuration. This test did not encounter queue waiting; the implementing task's
installed-runtime and original-endpoint concurrency evidence establishes FIFO and
cancellation separately. Compose/environment and Bindery settings inspection
found no other Byparr browser consumer in CT120. CT100 has no Docker/runtime
consumer. Lidarr and other users of Prowlarr are indirect consumers.

The original Saturday updater `/usr/local/sbin/update-minipc-leftover-services.sh`
unconditionally called `docker compose pull` for Byparr. The current Compose pin
is a local image ID, not a published registry repository reference. Pulling an
image requires a repository name/tag or repository@digest; see the
[Docker reference](https://docs.docker.com/reference/cli/docker/image/pull/).
With `set -e`, that incompatible step can prevent later service updates.
The custom runtime must continue to be updated through its reviewed source/build
workflow, not the generic registry updater. The cron remains Saturday 05:45.

The original maintenance probe accepted redirects and even 404 at `/`. It does
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
- S2: The initial unqueued proxy test established connectivity only. The
  corrected qualification demonstrates an actual queued timeout in ordinary
  mode and successful completion in queue-aware mode. Execution budgets remain
  unchanged; the Prowlarr solver HTTP deadline is now independent. Telefonillo/Morphe adaptation remains with
  their existing owners; this assessment introduced no duplicate client edits.
- S3: Generic registry updates no longer pull or recreate the reviewed local
  Byparr image. Prowlarr's qualified queue-client image is also protected under
  S6. Remaining compose_update calls, backup behavior and cron are unchanged.
  The Byparr HTTP probe now requires `/ready` status 200.
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

The initial maintenance delivery did not restart services. The corrected queue
client deployment recreates only Prowlarr, preserving all Byparr endpoints and
resource caps. Execution budgets are unchanged and no upstream action is replayed.
S5-S6 final reconciliation supersedes the initial incomplete compatibility claim.

## Corrected final reconciliation

- S1-S2: The current queue-feedback image, original endpoints, one-browser
  ownership and resource caps remain unchanged. Prowlarr is the active direct
  server consumer; independently owned client tasks were not modified.
- S3-S4: The original Byparr maintenance fixes remain, and only Prowlarr's stock
  update call is additionally excluded for its qualified client patch. The
  tracked script matches deployed SHA-256
  `e038e9c12e41f8d045c041d69a2db1267bbaaac8df271dac9637baf1cc366bda`;
  actual Linux shell syntax, backup/lock contracts and other update calls pass.
- S5: The exact installed upstream source reproduces the 125-second HTTP
  deadline while maxTimeout=120000. The scoped queue-aware checkbox separates
  waiting using the dispatcher's supported InfiniteTimeSpan and preserves the
  original GET/POST behavior when disabled. Focused compiled regressions pass.
- S6: Actual Prowlarr requests entered production Byparr's FIFO. The scaled
  stock client deadline failed, while the patched isolated and production
  clients survived the same queue hold and completed successfully. Production
  SQLite independently confirms persisted waitForQueue=true, original host and
  120-second execution budget. Only Prowlarr was recreated; Byparr's ID/image and
  one CPU/2 GiB caps remain unchanged, with no OOM or restarts. Production system
  status and normal proxy test return 200. The pinned Compose image/no-pull
  setting, Docker update mechanism and guarded weekly script preserve the patch.
  Reproducible source/build/test/deploy artifacts and rollback are in
  `tools/prowlarr-queue/README.md`.

The disposable test container, its tmpfs configuration, HTTP fixture, transfer
files and D:/Temp validation clone/packages/build outputs are removed. Reviewed
cleanup transaction `9cffefec576c0957b15e3d5cab37a12a` is applied with no exclusions
or residual failures. The small server image reconstruction context is an
intentional recovery artifact. The existing weekly reminder now includes the
Prowlarr queue-client upgrade gate, without changing its schedule or permitting
automatic production changes. The one-time follow-up remains paused.

No required blockers or deferrals remain. This qualifies the Prowlarr solver
boundary, not unlimited latency guarantees for indirect clients' separate HTTP
deadlines. No full-stack compatibility guarantee is asserted.
