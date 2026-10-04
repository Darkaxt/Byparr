# Prowlarr queue-compatible client

This narrowly scoped patch targets Prowlarr 2.6.5.5623, upstream commit
`12c327808314a7cae1b7301935ee10cabc19609f` (GPL-3.0).
It adds the advanced `Wait for Solver Queue` checkbox, default false. Only the
existing Byparr proxy has it enabled. Solver `maxTimeout` remains 120000 ms.
Queue-enabled solver HTTP requests use .NET `Timeout.InfiniteTimeSpan`; ordinary
solver requests retain execution timeout plus five seconds. No request replay,
queue deadline, new browser or Byparr runtime modification is introduced.

## Qualification

`FlareSolverrQueueFixture.cs` fails on stock queue-aware GET/POST cases and passes
after the patch, including unchanged ordinary GET/POST deadline behavior.
`build.ps1 -WorkDirectory D:/Temp/prowlarr-queue-build` clones the pinned source,
applies the patch and builds/tests with SDK 8.0 (qualified with 8.0.425).
The upstream style configuration is supplied explicitly via SolutionDir.
Only the managed `Prowlarr.Core.dll` changes in the pinned Linuxserver image;
all platform/native libraries and runtime files remain original.

Run `verify_queued.py` inside CT120. Default targets the disposable qualification
instance (19696); `--container prowlarr --port 9696 --only-queue` targets production.
It creates one temporary bridge-only HTTP fixture and two harmless browser
operations. Proxy test settings are in-memory API test payloads, not saved edits.
It refuses to start while existing browser work is active. Diagnostic observation
at 16 seconds tests the old 15-second external deadline; it does not cancel the
operation. The fixture releases through an event and the browser returns normally.
Never run this test concurrently with another qualification or busy browser work.

2026-10-04 evidence:

- Stock-mode actual client timed out in the FIFO: HTTP 400 after 15.8 seconds.
- Isolated queue-aware client survived the 16-second hold: HTTP 200 after 22.41 s.
- Deployed queue-aware client survived the same hold: HTTP 200 after 22.01 s.
- Test execution budget was scaled to 10 seconds; source regression separately
  verifies the saved production 120-second budget is passed as 120000 ms.
- Production SQLite independently contains `waitForQueue=true`, timeout 120,
  original host `http://byparr:8191/` and the original proxy ID 1.

## Persistent deployment

`deploy.py` runs inside CT120, holds the existing maintenance lock, checks the
stock image and previous updater checksum, installs an immutable local image pin
with `pull_policy: never`, and recreates only Prowlarr. It enables the option via
the normal API, preserves other settings and restores prior state on failure.
It is deliberately guarded, not an idempotent general-purpose deployment engine.

Live image: `sha256:bb59a065e316bc9f66af4bc2906c70f8a155c924381a3e83cbbc48dc155e4b25`.
Core DLL SHA-256: `465b2e8807168ed6b46dd769ddf3865f82555403aebebe45bc21509a5843e405`.
The build context `/opt/prowlarr/queue-build` is retained intentionally (about
2.2 MB) to reconstruct this image without installing an SDK on the server.
Settings remain in the existing persistent `/opt/prowlarr/config` mount.
Prowlarr's update mechanism is Docker, not its built-in updater. The weekly
maintenance script skips stock registry replacement of both custom solver and
custom client; remaining updates and existing cron/backup/locking are preserved.

Prowlarr upgrades now need explicit qualification: rebase this small patch onto
the selected version, run focused source and actual queued tests, then rebuild
against the matching pinned base. Do not silently overwrite it with `latest`.
The existing weekly Byparr review should include this client compatibility gate.

## Rollback

While the patched runtime is still running, disable `Wait for Solver Queue` on
proxy ID 1 via its normal API/UI, retaining requestTimeout=120 and its host.
Change only the Compose image to the retained stock image
`sha256:f2b26429893d4c4cb71941b7ee50b1bdecd9d5f9f9e02d5410615e9f4f7c8d95` and recreate
only Prowlarr with `docker compose -f /opt/prowlarr/compose.yaml up -d --no-deps
--pull never prowlarr`. No database migration or data restore is necessary.
Check system status and proxy test. Rollback restores the known queue deadline
incompatibility, so it is recovery, not a queue-compatible solution.

## Boundaries

Queue-full 503 and genuine upstream/browser failures still fail the indexer
operation, rather than crashing Prowlarr. A disconnected/down solver connection
still fails normally. An indefinitely hung but connected solver can retain the
waiter: arbitrary timer-based cancellation was intentionally not added.
This fixes Prowlarr's solver boundary; it does not remove unrelated HTTP deadlines
in external search clients or guarantee unlimited queue latency to those clients.
Morphe and Telefonillo remain managed by their own tasks; this patch does not
claim to qualify their independent integrations.
