# Weekly maintenance, 2026-10-12

Authorization: already_authorized. The weekly maintenance instruction includes
review, integration, qualification, commit/push, deployment and transactional
cleanup. This record applies the existing POST, scripting, transactional admission,
queue feedback and Prowlarr compatibility specifications; it does not replace them.

## Scope and acceptance criteria

- M1: Review upstream `8bcc5e89c4e3378fb9559b2899b9d285fa1b69db` through
  `4e4e76ffed6aab08091c6f161e648a5dd0600dc7`. Integrate applicable fixes while
  preserving the fork contracts and other tasks' work. Record exclusions explicitly.
- M2: Verify changed behavior and existing POST/redirect/script/admission contracts
  using focused tests and the actual installed browser. A fresh original-endpoint
  Uptodown resolution/native original-APK check is required for this browser
  configuration change. Preserve a single browser during qualification.
- M3: Deploy the qualified image only to the existing Byparr service, preserving
  original endpoints/network/privacy, resource/security/storage/log settings and
  Prowlarr's pinned queue-aware image, identity and saved settings. Verify the
  original endpoint, real browser operation, health, queue and Prowlarr consumer.
- M4: Preserve the running qualified image/configuration during replacement and
  automatically restore them on qualification/deployment failure. Remove only
  reviewed task staging/test containers and unused superseded task images after
  success. Retain compact evidence and reproducible source; commit/push the
  completed result to origin/custom-post.

## Review decisions

The production runtime remains pinned to the existing immutable base, Invisible
Playwright 0.7.2 / invisible-core 20.15.0 / FastAPI 0.141.1 / trafilatura 2.2.0.
Production and repository worktrees were unchanged at preflight; the prior
verified Prowlarr client commit `703df0d` is local and will be included in delivery.

Applicable changes: `e65d809` (Uvicorn log level), `bfa03a4` plus `a5e903e`
(normal response cookies scoped to requested/final URL), `4e4340d` (disable
HTTPS-First navigation upgrade). Scripted response cookies continue to include
capture URLs, as required for native attachment handoff.

The settled-HTML fix in `c653b10` / `80dc9fc` is already implemented equivalently:
the fork reads HTML after its normal network-idle wait. Preserve scripted
navigation behavior and POST replay detection rather than replacing that logic.
Existing production tmpfs, shared memory and log bounds already satisfy the
disk-wear guidance; do not import upstream's misplaced build-only Compose fields.

Do not upgrade the qualified runtime implicitly. Upstream's vendored-error
imports and three-argument geolocation API require Invisible Playwright >=0.15;
live inspection confirms 0.7.2 exports neither Error nor TimeoutError, and its
prepare_session_geo takes two arguments. Those dependency/browser-dependent
changes are inapplicable to this pinned deployment. FastAPI/trafilatura/Ruff,
Ubuntu and lockfile updates are not deployed without a corresponding runtime
upgrade and qualification. Selective integration retains ancestry accurately;
the complete upstream main is reviewed, not recorded as fully merged.

## Stages and reconciliation

| Stage | Status | Criteria | Evidence |
| --- | --- | --- | --- |
| Compatible integration and qualification | COMPLETE | M1; M2 controlled fixtures | Reviewed selective integration; old-image regressions fail and candidate checks pass; installed cookie/GET/POST/redirect/replay/script/CSP/frame/cleanup fixtures and real HTTP FIFO/feedback/disconnect/overload checks pass with no OOM or PID-limit events |
| Production delivery and cleanup | COMPLETE | M2 original-endpoint Uptodown; M3-M4 | Live Uptodown/native APK and Prowlarr proxy pass; deployed service healthy; staging/test containers/superseded image removed; verified implementation 3ee93e4 committed and pushed to origin/custom-post |

Blockers: none after Tailscale SSH reauthentication. Tracked deferrals: none.
Runtime upgrades excluded above are review decisions, not claims of delivered
upstream dependency compatibility.

Recovery: keep the exact pre-cutover Compose bytes and current image ID for this
operation only. Stop production before starting a browser qualification instance.
On any failure, remove the qualification instance, restore the saved Compose
bytes and start only the original Byparr service, then verify readiness and a real
browser request. On success, remove the old image only after confirming it has
no container consumers, and remove the temporary Compose snapshot/staging.

## Verification and delivery evidence

The selected upstream changes are integrated with attribution in this record.
The only browser-launch conflict was resolved by retaining admission ownership
and cleanup around InvisiblePlaywright and adding the upstream HTTP preference.
No browser/dependency upgrade, Prowlarr rebuild, saved consumer edit or unrelated
service upgrade occurred.

Focused checks ran against the installed production dependency versions in a
disposable, limited container. Cookie-scoping and HTTP-preference regressions
fail against the previous production image and pass against the candidate.
POST/script/admission/offline navigation contracts pass. The existing updater
checks pass separately in their repository context. Test harness dependencies
were isolated from application dependencies and removed after qualification.
Affected Ruff lint/format and whitespace checks pass.

Installed-browser controlled fixtures pass GET/form/JSON Unicode POST, same-context
cookies, 303/307/308 body/method behavior, cross-origin credential stripping,
actual 422/503 responses and explicit one-replay handling. Script fixtures pass
initialization, awaited output, native input, main-document binding isolation,
CSP behavior, pre-transfer capture, navigation-retained output, cancellation,
budget handling and cleanup. Actual HTTP tests prove FIFO, cancelled waiters with
zero submissions, the 16-waiter bound/503, responsive readiness, duplicate-ID 409,
moving feedback and removal of finished identities. API qualification measured
843599872 bytes and 239 PIDs, with zero OOM/PID-limit events; the separate script
fixture measured 817508352 bytes and 300 PIDs. These are observed peaks, not
reservations or universal maximum requirements.

Live original-endpoint Uptodown verification resolved Showly file `1220892131`,
captured the attachment before transfer, and downloaded the original APK through
native HTTP: status 200, 12004991 bytes, SHA-256
`f0fac7fc5474168ca982fd220361f3bbb76d4f4f3ed9e89cf03d2465d2b77074`.
This is a fresh successful Turnstile/browser flow on this occasion, not a promise
that every future challenge will accept the browser.

Current deployment:

- Image: `sha256:c4d4b0cd1851cc9d222a7ed1fe3bb4c956abc10b8fd4363043edf505166b3b2d`.
- Source label: `source-sha256:6daa5767c2bb02a8e9d1ee5c282ed5f61d5b92de1d357bd66fef08f2d168c6c4`.
  This hashes compact sorted JSON mapping each shipped main/src/adapter Python
  path to its SHA-256 after CRLF-to-LF normalization. Installed files match that
  manifest. Test-only `runtime/__init__.py` is not shipped or included.
- Original localhost/Docker/Tailscale port 8191, private routing, network, DNS,
  environment mappings, one CPU, 2 GiB without extra swap, 512 PIDs, non-root,
  read-only/capability restrictions, tmpfs/shared-memory/log bounds, restart policy
  and browser-free health configuration are unchanged.
- Prowlarr retains image `sha256:bb59a065e316bc9f66af4bc2906c70f8a155c924381a3e83cbbc48dc155e4b25`
  and its original container identity. Proxy ID 1 test returns 200, with
  `waitForQueue=true`, execution budget 120 seconds and original Byparr host.
- The updater still matches SHA-256
  `e038e9c12e41f8d045c041d69a2db1267bbaaac8df271dac9637baf1cc366bda`;
  stock registry replacement remains excluded for both custom pins.

Two operator verification errors exercised recovery before live acceptance:
the first manifest incorrectly included an unshipped test-only file; the second
compared environment list order instead of mappings. Both restored the previous
qualified image/configuration and verified a real browser request. After fixing
those checks, the final candidate passed installed-source and environment checks,
Prowlarr and Uptodown; no application changes were needed for either recovery.

Reviewed remote cleanup removed 646 staging files (7630758 bytes), their empty
directories and the unused superseded image `7da2c6b4295b`; no broad Docker prune
was used. Local transaction `51aa63db09206f88432f498593c3fb1e` removed the dedicated
scratch/cache/APK tree with no exclusions, failures or residual files. Exact
hard-link names were authorized without deleting external names. The earlier
unused stricter review was discarded. Compact server evidence remains at
`/opt/byparr/maintenance-20261012-evidence.json`, and private qualification/live
evidence is under repository `local-evidence/maintenance-20261012`.

After cleanup the original HTTPS readiness endpoint returns 200, and a fresh
browser GET returns API ok, target 200 and the expected document. Docker reports
healthy, zero restarts and no OOM kill. There are no unresolved verification
blockers or tracked deferrals. Implementation commit `3ee93e4` is verified on
origin/custom-post, including delivery of the earlier verified Prowlarr client
commit `703df0d`. GitHub Actions remain disabled. The final read-only server check
confirms the new image is healthy with zero restarts/OOM and the original Prowlarr
identity/image; host memory PSI averages are zero. Both stages are COMPLETE;
M1-M4 are satisfied, with the runtime exclusions above stated explicitly.

## Weekly review, 2026-10-19

Reviewed upstream `4e4e76f..5c3681129d02c849b50bfd621c1333cc8d51ce10`:
`405a45b` updates Playwright to 1.64 and `5c36811` updates test-only httpx2/httpcore2
to 2.14. The complete delta changes only dependency declarations and their lockfile;
there is no application, adapter, admission or consumer fix to integrate into the
qualified immutable runtime. The runtime-upgrade exclusions above still apply.
No application/deployment configuration or live service was changed, and no
build, restart, replacement or recovery was needed. The original HTTPS endpoint
passed browser-free readiness and a fresh browser GET (API ok, target 200,
expected document). No new actionable condition or task-generated scratch exists.

## Weekly review, 2026-10-26

Reviewed upstream `5c36811..96e49b71a18f1cd8cb8ae1779f3de9076b6a22ee`:
`94ae1e7` and `96e49b7` update test-only httpx2/httpcore2 through 2.16. The complete
delta affects only test dependency declarations and lockfile package records;
application, browser, adapter, admission and consumer code are unchanged. Retain
the test-client versions used by the existing qualification profile, consistently
with the previous review; these updates supply no production behavior change to
deploy. No build, restart, deployment, release or recovery was performed. Original
HTTPS readiness and one fresh browser GET passed (API ok, target 200, expected
document). No production configuration or saved consumer settings were edited,
and no expendable task scratch was generated.

## Weekly review, 2026-11-02

Authorization remains already_authorized. Review range:
`96e49b71a18f1cd8cb8ae1779f3de9076b6a22ee..3d34b33ff82ec6e087eb21dd7449efee2062960a`.
The worktree was clean and origin/custom-post matched the verified November 1
repair before this review. That deployed repair and current pins are authoritative
in `apkmirror-profile-spec.md` and `compose.production.yaml`; this review must
preserve its classifier and validated atomic GeoIP publication patch as well as
the earlier POST/script/queue/Prowlarr contracts.

Current maintenance acceptance:

- W1: Review the complete upstream delta, integrate applicable changes and
  record precise provenance/exclusions without changing the qualified runtime.
- W2: Verify the changed lock record against upstream and unchanged runtime
  inputs. Verify original-endpoint readiness and a real safe browser GET. Read
  back deployed image/resources and Prowlarr's pin/settings/update exclusion
  through the existing authenticated administration channel.
- W3: Commit/push verified preparation, clean exact task scratch and record any
  external impediment accurately. No unnecessary rebuild, restart or replacement
  for a test-only dependency update; no new rollback image or unrelated upgrade.

| Stage | Status | Criteria | Evidence / remaining acceptance |
| --- | --- | --- | --- |
| Weekly compatible integration and verification | BLOCKED | W1-W3 | W1 and lock/original-endpoint parts of W2 verified; W3 scratch cleanup complete and reviewed source prepared for synchronization; W2 administrative inspection requires renewed Tailscale authentication |

`6be4b57` is selected for the test dependency setuptools 84.0.0 -> 84.2.1.
Its title says 84.1.0, but the actual reviewed patch installs 84.2.1; use the
actual artifact/version hashes. Upstream PR 442 describes
[GHSA-xmj3-9gf7-h52w](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w):
a Windows path escape when legacy wheel-as-egg installation processes crafted
namespace metadata. This test/build dependency update is applicable to the
Windows development checkout; it does not establish exposure of the Linux
production service and does not change its immutable image. No exploitation
probe or dependency installation is required for this lock-only integration.

`3d34b33` updates test-only pytest 9.1 -> 9.2. Retain the previously qualified
test runner rather than broadening this maintenance into a test-toolchain upgrade.
No upstream application, browser, adapter, admission or client code changed.
Review through upstream main is selective integration, not a claim of full merge.

The exact setuptools package record matches upstream, including the locked wheel
SHA-256 `ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2`.
Parsed TOML comparison proves every other lock package/metadata record and all
application, runtime, production Compose and client inputs remain unchanged.
Original HTTPS readiness and a fresh safe browser GET passed (API/target 200,
expected Example Domain document). Private verification receipt:
`D:/Artifacts/Byparr/2026-11-02-maintenance/review-verification.json`.

The original HTTPS readiness endpoint currently returns 200. The supported
Proxmox SSH route instead requests a renewed Tailscale check before executing
the read-only Docker inspection; no alternate administration route or credential
change is attempted. Therefore fresh deployed image/resource/Prowlarr checks
remain unverified. No administrative server command, deployment or recovery has
been performed. Both task-owned pending SSH checks were closed; no waiting
administrative operation remains to be resumed or duplicated.

External blocker: W2's fresh Docker image/resource and Prowlarr identity, settings
and updater-pin inspection cannot run until Tailscale SSH reauthentication for
root@100.74.127.101 is completed. Overall maintenance verification remains
incomplete. Next action after authentication: inspect the actual existing Byparr
and Prowlarr deployments/settings/updater exclusions through pct exec 120; make
no replacement unless that inspection establishes a new actionable condition.
No fresh browser/runtime qualification or Uptodown download is required by this
test-only lock change. The November 1 runtime remains the intended deployment.
Debt assessment: exact upstream lock-record selection adds no runtime control
flow, adapter, queue owner or new abstraction; no consolidation is required.

No required work is deferred or dropped. W2 is parked on the external
authentication prerequisite, not classified as complete; no later stage is
active. Transaction `1c95265f540ca012752066b967daa6fa` removed both reviewed
scratch members (3064 logical bytes), without exclusions, errors or residuals;
the exact E: scratch root is absent. Only the compact review/cleanup receipts
remain intentionally in the D: evidence folder. The recall helper again reported
SQLite `database is locked`; status confirms a stale, unlocked cache. No recall
refresh or SSH operation remains running. Visible history, current repository
diffs and live HTTP evidence were used instead of claiming fresh cached recall.
