# APKMirror challenge and GeoIP repair, 2026-11-01

Authorization: already_authorized by the request to fix the reported Byparr
failures. Investigation, implementation, verification, commit/push and qualified
delivery to the existing private server are included. Earlier handoff documents
are evidence, not new instructions or authorization limits.

## Requirements and acceptance

- A1: Establish the installed profile and challenge failure with live evidence.
  Inspect real launch flags, cached GeoIP validity/capacity and one controlled
  safe APKMirror page GET with terminal challenge evidence. Distinguish a fixed
  profile defect from demonstrated challenge clearance.
- A2: Correct invalid/partial GeoIP cache selection and publication at its source.
  Publish only a validated complete database; retain a valid cached database on
  refresh failure. Bound storage to a measured refresh budget and retain the
  service's total one CPU/2 GiB/no-extra-swap/512-PID limits, security, private
  network/routing and original endpoints. No arbitrary retries, increased solve
  budgets, IP/provider changes or unrelated consumer reconfiguration.
  Correct the reproduced interstitial false positive as well: Cloudflare's
  background precursor/JavaScript-detection scripts on a completed target page
  must not keep the solver waiting. Preserve detection and timeout of genuine
  interstitials and the explicit POST replay contract.
- A3: Verify the reported YouTube, YouTube Music and Amazon Shopping build pages
  through the original Byparr endpoint with maxTimeout=60000, actual successful
  target HTML and no remaining challenge. Do not download or install these APKs.
  A profile repair alone does not satisfy this requirement.
- A4: Preserve and qualify browser POST, explicit replay, status/body, redirects,
  scripting/native input/CSP/frame isolation/capture, one-browser FIFO/feedback/
  cancellation and cleanup. Runtime patch changes also require fresh original
  Uptodown resolution and native original-APK hash verification. Preserve the
  queue-aware Prowlarr image, settings and 120-second execution budget; test the
  consumer after deployment.
- A5: Use controlled, recoverable qualification/replacement with no overlapping
  Byparr browser instances. Preserve the last qualified image/configuration for
  that operation only; restore and verify them on a failed replacement. Record
  results, reconcile all criteria, commit/push verified source and deployment,
  clean exact expendable task artifacts through supported procedures and verify
  the actual delivered service. No unrelated services or external releases.

## Evidence and current decisions

The supplied report is retained at
`D:/Artifacts/Morphe-Extended/diagnostics/2026-11-01-byparr-408/report.md`.
Current working evidence is retained at
`D:/Artifacts/Byparr/2026-11-01-apkmirror`. Disposable scripts use
`E:/Temp/byparr-apkmirror-20261101`; cleanup transaction
`b6359416469609b87050bd02e5890d84` covers that exact root.

Live inspection confirms Invisible Playwright 0.7.2, invisible-core 20.15.0,
Playwright 1.60.0, playwright-captcha 0.1.5 and maxminddb 3.1.1. Firefox uses
`-juggler-pipe`, with no remote-debugging-port=0 flag. No browser/profile/IP
replacement is justified by that hypothesis.

The 128 MiB GeoIP tmpfs is completely full. It contains a valid 120900681-byte
October 7 GeoIP2-City database and an invalid 13316096-byte October 14 file with
no MaxMind metadata marker. The installed loader extracts a replacement before
pruning old data, and subsequently trusts target existence rather than validity.
This explains a truncated replacement being selected indefinitely. It establishes
the cache/profile defect, not the cause of Cloudflare's rejection.

The isolated baseline reproduces HTTP 408 with maxTimeout=60000, yet terminal
HTML and screenshot show the actual Amazon 32.19.0.100 APKMirror download page.
Its remaining script is `/cdn-cgi/challenge-platform/scripts/precursor/main.js`.
The installed captcha dependency detects an interstitial using ANY script under
`/cdn-cgi/challenge-platform/`, so it cannot recognize clearance on this page.
This is direct evidence for a false-positive timeout, separate from the GeoIP
defect. Background precursor and JavaScript-detection paths must be excluded
without accepting unknown/genuine challenge scripts. Baseline used one bounded
isolated browser; original production was restarted and all diagnostic Docker
containers/volume were removed after retained evidence was retrieved.

The GeoIP refresh budget is increased from 128 to 256 MiB, still within the
unchanged 2 GiB service cap. This allows measured old+new database sizes (about
121 MB each) during same-filesystem atomic replacement; the compressed archive
uses the separately bounded /tmp. On extraction/validation/space failure, retain
the previous valid database rather than publishing the incomplete replacement.

## Stages and reconciliation

| Stage | Status | Acceptance | Current evidence / advancement blockers |
| --- | --- | --- | --- |
| Cohesive repair, installed qualification and delivery | COMPLETE | A1-A5 | Root causes reproduced; installed and original-endpoint acceptance passed; private service delivered, source synchronized and exact cleanup verified |

The two original plan rows were consolidated because qualification
must cover the complete connected fix, including both causes, before acceptance.
No required criteria were removed. All acceptance criteria passed within this
single stage. Blockers: none. Tracked deferrals: none.

Candidate `sha256:6449088f52aca11c19bc55d1a7a5531b6cdb13bf9a531aa2a1068da55ea9823e`
passes the real-reader cache lifecycle tests (the previous image fails their
behavioral assertions). Installed-browser classification verifies background
scripts, genuine interstitial detection, clearance and target body delivery.
The private Amazon comparison returns API/target 200 with the correct build;
the same baseline flow returned 408 while its terminal page was already real
content. Both profiles report en-US/Asia-Nicosia; do not attribute this clearance
to a locale change.

## Installed qualification and delivery

The immutable base remains
`ghcr.io/thephaseless/byparr@sha256:874f719518f617d03a60e03411fc5d090647e1a877041e81f8dc965927c7deb6`.
No browser or dependency version changed. Candidate tag:
`local/byparr-post:apkmirror-20261101`; image ID is recorded above and pinned in
`compose.production.yaml`. Shipped-source digest:
`8674c816df469e72ced6f6b7d57fed3638745ce971127d32cd16aef92544dedd`;
installed patched GeoIP loader SHA-256:
`edbea72c17d941cbbdd169c5909798084206d2859f9ad3c0f5c5b2d67ad56eac`.
The installed manifest matches newline-normalized main.py, src/*.py and all
runtime/patch_*.py. The staging helper now includes every runtime patch instead
of dropping the existing scripting patch and new GeoIP patch.

Real installed-browser and concurrent HTTP verification passed:

- GET/form/JSON UTF-8, preflight cookies, actual 422/503 status/body, 303/307/308
  uploads and cross-origin credential stripping; default one submission versus
  explicitly permitted challenge replay.
- initScript/async script/arguments, HttpOnly cookies, CSP, isolated bindings,
  main-document native helpers, child-frame boundaries, popup/navigation capture
  before attachment transfer and navigation-retained output.
- FIFO single-browser admission, browser-free readiness and live UUID positions,
  duplicate-ID rejection, queue overflow, queued disconnect/cancellation with no
  target submission, cleanup before handoff and removal of completed feedback.

The script fixture peaked at 1049542656 bytes and 246 PIDs, with zero memory/PID
events and nine final PIDs. GeoIP lifecycle tests run with the installed runtime
and the synthetic MaxMind fixture: `python /work/tests/geoip_test.py` with this
repository's tests mounted at /work/tests. They use no network or new dependency.
The rendered classifier fixture is `tests/challenge_classification_integration.py`.
Run browser fixtures only in the documented isolated single-browser maintenance
window, never concurrently with production.

Original HTTPS endpoint acceptance used maxTimeout=60000 unchanged:

| Requested APKMirror build | API / target | Correct build and download button | Elapsed seconds |
| --- | --- | --- | --- |
| YouTube 21.30.216 | 200 / 200 | verified | 21.08 |
| YouTube Music 9.30.53 | 200 / 200 | verified | 19.22 |
| Amazon Shopping 32.19.0.100 | 200 / 200 | verified | 20.49 |

Exact URLs, target HTML and thin proofs remain in private working evidence;
no APKMirror APK was downloaded or installed. This establishes clearance for
these live requests, not universal future Cloudflare compatibility.

Fresh original-endpoint Showly 3.72.0 build 1220892131 resolution captured its
attachment URL before transfer, then native HTTP downloaded 12004991 bytes.
APK SHA-256 `f0fac7fc5474168ca982fd220361f3bbb76d4f4f3ed9e89cf03d2465d2b77074`
matches the independent Helium original. Signed URLs/cookies are private evidence.
Prowlarr's actual proxy test returned 200; container identity, qualified queue
image, original host and saved 120-second execution budget/settings are unchanged.

Transactional replacement preserved the original endpoint/name/network/DNS,
private routing and resource/security limits. An evidence-writer Unicode error
in the first live check caused the supervisor to restore the previous image and
verify a real GET. After fixing UTF-8 output, the identical qualified candidate
was delivered and accepted after all live checks. No fixture rerun was necessary
for that operator-only correction. The final service is healthy, zero restarts,
no OOM kill, with a valid 120618300-byte October 28 GeoIP database. Compact server
receipt: `/opt/byparr/apkmirror-20261101-evidence.json`.

Debt assessment: the narrow classifier and guarded installed-loader patch address
the two reproduced defects without adding runtime services or duplicate browser
ownership. Patch anchors intentionally fail the build if the pinned loader changes;
review/requalify rather than bypassing them. Future GeoIP growth can exceed a
bounded refresh budget, but failed publication retains the valid cache. Source
recovery uses the recorded commit, pinned base and production Compose; obsolete
custom images are retained only during an active replacement transaction.

## Final reconciliation

- A1 satisfied: inspected launch/profile/cache and reproduced the false timeout
  with terminal DOM/screenshot evidence, without blaming an unobserved browser flag.
- A2 satisfied: installed-reader tests reject truncated/invalid data, retain the
  valid cache on ENOSPC/refresh failure and prove atomic publication. Rendered
  browser checks prove real interstitial detection and background-script clearance.
- A3 satisfied: all three exact reported build pages passed original-endpoint
  API/target 200 with correct content and unchanged solve budgets.
- A4 satisfied: actual browser/HTTP preservation fixtures and fresh original
  Uptodown/native APK verification passed. Prowlarr proxy test passed with its
  original identity, image and saved settings unchanged.
- A5 satisfied: candidate accepted after supervised recovery was itself exercised.
  Live Compose matches `compose.production.yaml` exactly. Implementation commit
  `0d389c05156b44a6d6a0ca8a4b1ee4c8573e4d2b` was pushed and read back from
  origin/custom-post; its shipped-source hashes match the installed manifest.
  Actual delivered image is healthy with zero restarts/OOM; readiness is 200.

The unused earlier trial image and superseded October 12 custom image were
removed through native Docker after checking consumers and closing recovery.
Task Docker containers/volumes are absent. Transaction
`b6359416469609b87050bd02e5890d84` removed all 17 reviewed local scratch members,
12056255 logical bytes, including the test APK and one-off scripts, with no
exclusions/errors/residuals. Compact cleanup/final-verification receipts and
the necessary diagnostic/qualification evidence remain in the D: evidence folder.
Source-based recovery uses this implementation commit and pinned immutable base;
no permanent rollback image or unrelated Docker pruning was introduced.

The installed recall helper currently fails its cache refresh with SQLite
`database is locked`, even though its thread status is unlocked. No refresh is
still running; do not claim cached recall is current or mutate its database.
The supplied report, visible task history and freshly inspected repository/runtime
provide the necessary evidence to continue this independent service repair.
