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
