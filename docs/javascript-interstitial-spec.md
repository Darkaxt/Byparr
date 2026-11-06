# JavaScript cookie/reload interstitial repair

Authorized 2026-11-06: correct the APKPure defect through investigation,
implementation, qualification, commit/push and private production delivery.
The supplied `byparr-handoff.md` is evidence; the user's instruction to carry
out the work supplies authorization. No phone action, APKPure APK acquisition,
version substitution or downloader validation change is part of this repair.

## Requirements

- J1: Verify production image/source and trace the observed inline cookie/reload
  interstitial through the actual installed browser. Distinguish captured failure
  from a demonstrated timing explanation; preserve historical evidence.
- J2: Wait for the observed interstitial's real document transition within the
  existing execution budget, or explicitly fail unresolved challenges. No blind
  delay, resubmission, cookie-value injection or generic retry cascade. Preserve
  final main-document URL/status/body consistency, including non-200 responses.
  The observed second-stage EdgeOne verification document must also be recognized.
  Wait for its real widget, activate the measured native checkbox at most once per
  navigation and await the main-document transition; remaining verification must
  fail explicitly. Public scripting helper frame/binding boundaries are unchanged.
- J3: Reproduce network idle before scheduled navigation with an actual browser
  fixture; verify completion, final non-200, unresolved transition and cancellation
  while pending, with resource/listener cleanup. Preserve POST replay permission,
  CF/background-script detection, ordinary HTML and scripted flows, single-browser
  FIFO, live feedback and queued disconnect behavior.
- J4: Qualify and deliver with the existing immutable runtime, original private
  endpoint, one CPU/2 GiB/512 PIDs, bounded storage/logs/security and preserved
  Prowlarr identity/pin/settings. Fresh live APKPure metadata must reach the exact
  package listing or be reported explicitly unresolved. Preserve fresh original
  Uptodown/native APK verification required by established browser delivery gates.
- J5: Hold a concrete recovery transaction during isolated qualification and
  replacement; restore and verify the previous service on failure. Commit/push
  verified source and configuration, clean exact expendable staging and old images
  after acceptance, and reconcile all requirements before completion.

## Stage and evidence

| Stage | Status | Requirements | Evidence / remaining acceptance |
| --- | --- | --- | --- |
| Integrated interstitial repair and private delivery | ACTIVE | J1-J5 | J1-J4 verified; qualified candidate accepted on original endpoint; J5 source synchronization, exact cleanup and completion report remain |

No tracked deferrals. J5 source synchronization, exact cleanup and the requested
completion report remain; they are being resolved within this single stage.
The earlier weekly administrative verification is satisfied by this delivery's
fresh image/resource/consumer/update-exclusion checks.

Production source label is
`source-sha256:8674c816df469e72ced6f6b7d57fed3638745ce971127d32cd16aef92544dedd`.
The existing Tailscale authentication check was completed by the user; original
SSH operation 96315 completed successfully and was not replayed.

Historical report and 1026-byte HTML remain untouched under
`D:/Artifacts/Morphe-Extended/diagnostics/apkpure-native-20261106`.
Retained task evidence: `D:/Artifacts/Byparr/2026-11-06-apkpure`.
Disposable scripts/APK: `E:/Temp/byparr-apkpure-20261106`, exact cleanup transaction
`9d25c5f1705e2d52332d8cd6b3f36e84`. Remote staging uses task-owned native Docker
volumes/containers; no unrelated workload or global Docker prune is authorized.

Installed baseline trace confirms the working explanation: the original request
returned the empty inline cookie interstitial at 1.120 seconds; its natural reload
response arrived at 1.700 and committed at 1.739. No server resubmission was made.
The next document was 2081 bytes and still lacked the exact package marker, so
navigation alone is not accepted as clearance. Production was restored and its
browser-free readiness verified after this isolated trace.

The original image fails the controlled browser regression by returning the
`/start/200` document before its scheduled transition. The first candidate follows
the transition and preserves final 200/503, but the strict-CSP case found that
bulk `all_text_contents` uses blocked evaluation. A selector-only revision failed
because Playwright `:has-text` excludes script contents. An installed adapter
probe establishes the correct DOM path: native `text_content` and `inner_html`
both read the script under strict CSP, while bulk evaluation fails and has-text
counts zero. The implementation uses native text_content, with no CSP bypass for
ordinary requests. These are unresolved implementation findings, not accepted
releases; production was restored after each isolated check and is healthy.

The cookie-only native-text candidate passed the initial browser fixture: final 200/503
documents, same-URL reload, blocked-script timeout, cancellation/cleanup before
the next request and default one submission versus explicitly permitted one POST
replay. Installed CF/background classification also passed. Its broader controlled
checks passed before the live EdgeOne finding described below; it was not promoted.

The user requests a completion report to the existing `Morphe Extended` chat
after verified delivery.
That report must distinguish corrected API completion from exact-version APK
availability; metadata clearance does not prove Plague Inc. 1.27.5 availability.

The cookie-only candidate passes the seven controlled installed-browser/HTTP
fixtures, but the live probe exposes a second false-success document: title
`Security Verification`, main `#captcha`, Tencent Cloud EdgeOne branding and
later `#tcaptcha_iframe_eo`. Its resources load successfully. In that cross-origin
widget, actual DOM/screenshot inspection identifies native `#verifyCheckbox`.
One trusted native click followed by natural main navigation reaches the exact
Plague Inc. package listing (239064 bytes, correct title/marker) in 10.809 seconds.
That diagnostic operation is completed; no repeated click or APK acquisition was
performed. Automatic recognition and one-attempt handling are now integrated.

Final qualification reruns the expanded interstitial fixture (EdgeOne 200/503,
script startup, unresolved/single-input and cancellation cases), existing CF and
GET/POST/replay checks and actual HTTP/feedback fixtures. Earlier inspected
cross-origin redirect and script/CSP/binding/capture/budget results are retained
for unchanged adapter/helper code and normal-page behavior; no runtime upgrade
or public helper change invalidates them. New EdgeOne scripted behavior is tested
directly, and original-endpoint Uptodown capture/native hash remains required.

## Accepted private delivery

Version/tag `local/byparr-post:apkpure-20261106`, immutable image
`sha256:38c5c5c3910df6dc60b35168086901d42985d6dee4ca7eee29aa69f98f029020`,
shipped-source digest
`e8de629c37593d021671cf8a816b7e8d0ec4130dff18804980d5cb7bb882b646`.
Both the original deployed sources and candidate's installed sources were read
back and matched their normalized manifests. No dependency/browser/adapter
version or public scripting helper was changed.

Final current-image interstitial, CF, GET/POST/replay, real HTTP and live UUID
feedback fixtures pass. The expanded fixture verifies native EdgeOne 200/503,
script startup after verification, one input when verification persists,
unavailable-widget failure, pending-input/navigation task cancellation and POST
one-replay permission across both interstitial types. Browser fixture peak:
913588224 bytes/260 PIDs, zero memory/PID events. Earlier unchanged script/helper
qualification peak: 819355648 bytes/296 PIDs, zero memory/PID events.

Fresh ordinary original-endpoint request (no recipe/extra flag), UUID
`5509931e-bc74-42d1-8a81-5c2d9a38dfe5`, returned API/target 200 with the exact
`com.miniclip.plagueinc` package marker, correct title and 239291-byte listing.
Elapsed wall time was 23.58 seconds, including admission/setup; maxTimeout remained
60000. Returned HTML SHA-256:
`6d1f4a5c19bb6306b45e143d4fd373dea0443cd4e5e3104a2471e346a9e782fd`.
No APKPure APK or phone action was performed. Exact version 1.27.5 availability
and final APK identity remain the downloader's separate validation boundary.

Fresh original-endpoint Uptodown Showly 3.72.0/file 1220892131 verification passes:
pre-transfer attachment capture, native HTTP 200, 12004991-byte original APK,
SHA-256 `f0fac7fc5474168ca982fd220361f3bbb76d4f4f3ed9e89cf03d2465d2b77074`.
Only sanitized proof is retained; temporary signed response/cookies and the test
APK remain in the exact cleanup root until its final consumer exits.

Prowlarr proxy test returns 200. Its identity, start time/restart count, queue-aware
image, saved host/120-second execution budget/waitForQueue option are unchanged.
Production HostConfig/environment mappings match the previous service; private
8191 routing/Serve configuration, update exclusions and existing resource/security
limits are preserved. Compact server receipt:
`/opt/byparr/apkpure-20261106-evidence.json`. Replacement was accepted after all
live checks; no delivery rollback was required. Failed diagnostic/qualification
windows restored the previous service and verified readiness; no unrelated
service or registry upgrade occurred.

Debt assessment: document transitions have one listener owner in the existing
navigation function. Native EdgeOne click/navigation tasks are cancelled and
joined on every exit; one-attempt state prevents repeated input across unresolved
verification reloads. Recognition is based on observed challenge structure rather
than a hostname recipe or background scripts alone. No provider registry, public
command language, persistence layer or additional browser owner was added.
No consolidation is required to satisfy this scope.
