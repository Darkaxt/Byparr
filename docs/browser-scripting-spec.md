# Browser scripting and helpers: authoritative specification

Design agreed on 2026-10-03. Implementation, verification and original-endpoint
live qualification are already authorized by the user's instruction to proceed
and validate the Uptodown example. The complete applicable workflow includes
final reconciliation and a verified source commit.

## Outcome and integration boundary

Extend the existing private `/v1` service with optional browser JavaScript and
generic browser helpers. Morphe Downloader supplies the Uptodown recipe; Byparr
owns execution, browser events, admission, resource bounds and cleanup. Byparr
resolves a link; the companion downloads and validates the original file.

The API must remain generic. No Uptodown-specific branches, server-side recipe
registry, persistent sessions, pipeline interpreter, provider switch or browser
upgrade is required by this scope. Browser JavaScript is the scripting language;
server-side Python, shell execution and userscript-extension APIs are outside
the requested interface.

The original deployment remains the integration endpoint:
`https://media-apps-minipc.tail94fa2c.ts.net:8191/v1`.
The development instance stayed stopped outside bounded verification and was
removed during final cleanup at the user's request.

This follow-up introduces optional browser scripting beyond the completed POST
task's scope. It preserves that task's GET/POST, redirect, status and replay
contracts and the resource/lifecycle requirements in `production-promotion.md`.

## Required behavior and acceptance criteria

### B1: Optional script execution

- Accept optional `initScript`, `script` and JSON `scriptArgs` through `/v1`.
  Requests without them retain existing behavior and response semantics.
- Install initialization before the target website's scripts execute. Document
  its execution on navigation and frames; helpers must be ready before caller
  scripts use them. Initialization must not accidentally apply a target recipe
  to unrelated challenge frames.
- Evaluate `script` in the requested page's browser context after documented
  navigation readiness. Await its asynchronous result. Do not use network idle,
  an arbitrary sleep or an automatic repeated click as the business completion
  signal.
- Browser-owned user agent, cookies and existing egress remain in effect.
- Validate malformed requests and script/argument size bounds before launching
  a browser. Return a controlled error for invalid output or execution failure.
- Existing `request.post` challenge/replay rules remain authoritative: scripting
  does not silently permit replay of a submitted navigation or a website POST.

Verification: controlled fixtures establish initialization ordering, arguments,
asynchronous output, validation, script errors and unchanged ordinary GET/POST.

### B2: Native browser input

- Expose a generic native click helper callable from the supplied script. It
  uses Playwright input/actionability, rather than substituting DOM `.click()`.
- Locator failure and failed input return actual errors. Do not silently choose
  another element, bypass failed actionability or automatically replay a click.
- Provide the page/frame targeting needed by the first required real flow;
  neither unrestricted Playwright method dispatch nor a second command language
  is necessary.

Verification: a controlled fixture requires a trusted browser click; ambiguous
and missing targets fail. The Uptodown recipe activates its actual button.

### B3: Capture before attachment transfer

- Expose generic named request observation/interception through browser helpers.
  Registration completes before the helper returns; waiting for the event is a
  separate operation. This prevents a register-then-click race or deadlock.
- Request matching includes explicit URL and method constraints. Interception
  operates at browser-context scope, including an initial popup request, and
  cooperates with existing page routes without being bypassed by route priority.
- A matching attachment request can be captured and aborted before it is sent
  to the attachment server. Do not fetch the APK in Byparr, follow its redirects
  for validation, or wait for a download event that has already started transfer.
- Unmatched traffic continues normally, including the website's token-generating
  POST, Turnstile resources and the successful download-URL response.
- Website response observation, when needed for diagnostics or script results,
  captures failures as well as successes. Preserve the actual HTTP status and
  relevant error fields instead of masking a 400 response as an event timeout.

Verification: controlled fixtures establish pre-click registration, AJAX and
popup/navigation coverage, and zero requests reaching the attachment fixture.
The installed server Firefox must independently pass this boundary; generic
Playwright documentation alone is not proof for its download interception.

### B4: Results survive navigation

- Retain captured results in request-owned host state, outside page JavaScript.
  A page navigation or closed execution context must not erase a completed
  capture or turn successful capture into a false script failure.
- Define and document how a script chooses a named capture as its terminal
  result. Capture registration, selection and waiting must have unambiguous
  semantics; raw page-local variables are not a substitute for host retention.
- If navigation interrupts execution before the selected capture completes,
  report the actual execution/capture state. Do not manufacture success, restart
  the script, or replay earlier actions.
- Always dispose captures, listeners, pages and the browser on completion,
  failure, client cancellation or expiration of the existing API budget.

Verification: immediate post-click navigation destroys the script context while
the selected captured result remains retrievable; failure/cancellation cases
release admission and leave no browser or listener behind.

### B5: Structured output and privacy

- Return structured script output separately from ordinary page HTML. Retain the
  distinction between API success, captured target status and an attachment that
  has not been fetched. Do not label interception as an attachment HTTP 200.
- Include browser user agent and relevant cookies with their domain, path,
  expiry and secure scope. Preserve relevant captured request headers for native
  download; the companion must scope credentials to their destinations.
- Establish explicit script, argument, output, capture and page bounds. A script
  can neither remove the existing request budget nor acquire another browser.
- Do not log or commit scripts' secret arguments, tokens, cookies, signed URLs,
  full response bodies or private verification captures.

Verification: a typed output fixture remains distinct from page HTML, cookie
scope and request metadata survive capture, and oversize outputs fail cleanly.

### B6: Preserve server stability and existing consumers

- Keep one browser operation, immediate 429 without queuing/submission, cleanup
  before response delivery, and browser-free `/ready` monitoring.
- Preserve the original service name, network, Tailscale endpoint and port 8191.
  Preserve production limits of one CPU, 2 GiB memory, no extra swap, 512 PIDs,
  bounded writable storage/logs and the existing container protections.
- Enforce the existing API request budget from the host, including a hanging
  script or unresponsive page. Verify actual process cleanup; a JavaScript timer
  is insufficient. Add no unrelated deadlines, sleeps or retry policies.
- Use sequential verification, existing compatible runtime layers and a reviewed
  rollback. Do not leave an additional browser/container running, broaden Docker
  cleanup, or perform unrelated repair of the older cleanup blocker.

Verification: focused lifecycle/admission fixtures, resource/process evidence,
actual Prowlarr compatibility and the original endpoint after live qualification.

### B7: Fresh Uptodown acceptance

The acceptance flow is the requested Showly 3.72.0 build:
`https://showly-2-0.en.uptodown.com/android/download/1220892131-x`.

1. Open the exact build in Byparr through the original endpoint.
2. The supplied recipe derives application ID, file ID and options from the
   current page, checks the requested file ID `1220892131`, registers capture,
   and activates the actual button using native input.
3. That browser generates a fresh Turnstile token; the website submits its own
   POST and receives the actual successful download-URL response.
4. Capture the resulting signed attachment URL without transferring the APK
   inside Byparr. Return the preserved structured result and browser metadata.
5. A native HTTP client successfully downloads the original APK using that
   result. Verify file format, requested build and bytes against independent
   evidence. The handoff's historical size/hash are comparison evidence, not a
   substitute for fresh identity verification.

Do not substitute a captured token, empty token, fixture response, another build,
automatic retry or another browser/provider. A real Turnstile rejection remains
an unresolved live acceptance criterion even if controlled scripting tests pass.

The Morphe task owns subsequent Android integration, package/version validation
and unchanged bytes through the receiving URI. This Byparr scope must establish
the documented native download boundary without claiming those Android checks.

## Compact staged plan and reconciliation ledger

| Stage | Status | Requirements | Evidence required for closure |
| --- | --- | --- | --- |
| S1 Generic browser-script vertical slice | COMPLETE | B1-B5; lifecycle portions of B6 | Installed Firefox verified strict main-document CSP, uninjected child binding state, blocked worker registration, native input, AJAX/popup/navigation capture, retained failures, cancellation/CPU-bound cleanup and ordinary GET/POST/replay regressions |
| S2 Original-endpoint live qualification | COMPLETE | B6-B7 | Original HTTPS API 200; website resolution POST 200/success=1; signed request aborted before transfer; native APK 200, exact 3.72.0 package/version/hash; Prowlarr proxy test 200 unchanged; healthy/no browser/no restart/OOM/PID event, production caps preserved |
| S3 Final reconciliation and delivery | BLOCKED | B1-B7 | Runtime/source verification, source delivery, reminder and superseded-image cleanup pass; two empty cache markers remain policy-blocked |

Only one stage may be ACTIVE. Before starting S1, finalize the concrete helper
names and terminal-capture selection contract to implement the behaviors above.
These ordinary interface decisions must not remove or weaken any criterion.

A live differential diagnosis identified the original cross-frame binding as the
cause of widget error 600010: the same installed Firefox/network succeeded without
bindings and failed with only an exposed binding. The replacement excludes both
native export and controller initialization from child frames. S1 independently
verified that boundary; S2 then completed the fresh original-endpoint URL/native
APK workflow. This blocker is resolved.

S1 lifecycle evidence: memory.peak 794124288 bytes, pids.peak 295, no memory/PID-limit
events; ordinary-browser regression peak 895840256 bytes / 260 PIDs, no OOM or
PID-limit events. Full lifecycle evidence applies to the unchanged helper/capture
implementation; the final worker policy and frame-isolation fixture were refreshed
after rejecting the native preference comparison. Blockers: none. Tracked deferrals:
none. Final reconciliation and delivery remain owned by S3.

## Final reconciliation and cleanup

| Requirement | Verification |
| --- | --- |
| B1 | Initialization ordering, arguments, awaited output and controlled validation/error fixtures; ordinary GET/form/JSON POST and redirect/replay regressions |
| B2 | Trusted native click fixture, strict locator failures, frame targeting and fresh Uptodown button activation |
| B3 | Installed Firefox AJAX/popup/navigation interception fixtures with zero attachment-server requests; fresh website token POST finishes before signed request abort |
| B4 | Terminal capture survives destroyed page context; real disconnect, unresolved promise and CPU-bound budget expiry clean up and release admission |
| B5 | Separate typed output/HTML, scoped HttpOnly cookies, request metadata, finite JSON and output/capture/page bounds |
| B6 | Actual Prowlarr proxy test 200; original HTTPS readiness and healthy container; one CPU/2 GiB/512 PIDs, no OOM/restart, no browser after qualification |
| B7 | Exact Showly file 1220892131; fresh original-endpoint resolution, native HTTP 200, APK identity/version and independent SHA-256 match |

Final deployed module ASTs match the final source; source line endings were
normalized without changing behavior. Focused unit/contracts checks, installed
runtime integration fixtures, Ruff formatting/lint and diff whitespace checks
apply to that unchanged implementation. The existing weekly upstream reminder
was updated for Monday 09:00 Europe/Berlin; it does not autonomously deploy.

On 2026-10-03 the user explicitly required removal of the superseded image rather
than indefinite retention. Recovery rebuilds committed source `756127f`
against the immutable base pinned in its Dockerfile. The superseded image
`sha256:6bf4d2a0cb2397e99972d468aed830a3736bbc3f70cd90c8cf811e3b721ce9d5`, its
two tags, the stopped development container referencing it, and the temporary
rollback compose file were removed. No additional development container remains.
Original-endpoint readiness returned 200 and production remained healthy with
zero restarts after cleanup. A subsequent consumer browser operation is normal
service use; cleanup does not wait for or interrupt other consumers.
This authorized change replaces
the earlier stopped-development-container/retained-rollback-image arrangement.

Task-owned server staging `/opt/byparr-scripting` was removed after an exact
hash-reviewed snapshot. Compact evidence remains intentionally under
`/opt/byparr/browser-scripting-evidence.json`; private local evidence is gitignored.
Local cleanup reclaimed 521383928 bytes. Two zero-byte cache marker files under
`D:/Temp/byparr-browser-scripting/uv-cache/sdists-v9` remain: `.git` and `.gitignore`.

S3 blocker: required expendable-artifact cleanup cannot fully pass because
automatic approval review rejected exact deletion of those two verified empty
files as "blocked by policy." This is external to the implementation. It resolves
when deletion is permitted or the user removes those exact files and their empty
parent directories. Full S3/overall completion cannot be claimed while they remain.
No required work has been deferred to an unnamed future stage.

The replacement retains a native request-owned binding but narrows the bundled
Firefox adapter to main-document binding installation. Both its exported function
and the driver's binding-controller initialization are excluded from child frames.
A strict CSP fixture exposed an additional installed-runtime defect: requesting
`bypass_csp` did not remove a policy already attached to the document. The adapter
honors that explicit setting through Gecko's privileged policy-container API before
trusted main-document evaluation; challenge-frame policies remain untouched.
Scripted contexts block service-worker registration through the supported Playwright
context option. A native `dom.serviceWorkers.enabled=false` comparison disabled
Firefox’s download interception, so that preference remains unchanged. The worker
registration policy applies to all frames; helper bindings and target initialization
remain main-document-only.
Ordinary contexts retain their previous settings. These are narrow, fail-closed
adapter changes to the existing immutable runtime, with no browser/provider or
dependency upgrade. The discarded HTTP helper bridge is not part of the interface.

## Evidence and primary references

- Companion handoff:
  `C:/Users/darka/Documents/Projects/Android/Morphe-Manager-Downloaders/docs/uptodown-byparr-handoff.md`.
  Its successful Helium flow establishes feasibility in that browser, while the
  busy Byparr POST attempts establish no upstream POST result or POST defect.
- Local source inspection: `src/utils.py`, `src/models.py`, `src/endpoints.py`
  and `src/challenge.py` expose GET/POST navigation and isolated contexts, but
  no current public scripting/native-input/capture contract. Interstitial
  handling does not establish embedded widget compatibility.
- Playwright initialization:
  https://playwright.dev/python/docs/api/class-browsercontext#browser-context-add-init-script
- Playwright asynchronous evaluation:
  https://playwright.dev/python/docs/api/class-page#page-evaluate
- Native input/actionability:
  https://playwright.dev/python/docs/actionability
- Browser-context routing, popup coverage and page-route priority:
  https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route
- Cloudflare client-side widget execution:
  https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/

## Concrete interface decisions for S1

- `script` is a JavaScript function expression receiving `scriptArgs`; its JSON
  result is returned in `scriptResult.value`, separately from `solution.response`.
  `scriptResult.captures` contains named request/response records retained by the
  host. Normal navigation status and HTML remain in `solution`.
- `initScript` is a JavaScript body running before site scripts in the main
  document on the requested origin. It does not run in child frames or unrelated
  origins. Helpers are exposed before this initialization body.
- `byparr.click(selector)` performs native input in the caller's main document;
  an optional frame selector targets a child frame through Playwright.
- `byparr.watchRequest(name, options)` and `byparr.watchResponse(name, options)`
  register a named capture and return only after registration. Matching requires
  a method plus either an exact `url` or an origin-safe `urlPrefix`.
- `byparr.waitFor(name)` waits for that registered event and returns its record.
  `byparr.finishWith(name)` selects a request-owned terminal capture before an
  action; that capture completes the operation independently of page navigation.
  No helper automatically repeats a browser action or website POST.
- Request capture can set `abort: true` to prevent transfer. Response capture
  includes actual status and bounded JSON/text body, including failure responses.
  Both kinds preserve request URL/method/headers. Scripts remain responsible for
  selecting their intended build and interpreting application-level responses.
- Limits: 64 KiB UTF-8 per script and for serialized arguments, 1 MiB combined
  structured output/capture data, eight named captures and two pages per context.
  Scripting requires a positive existing `maxTimeout` budget. Invalid options
  fail before browser launch; script results and metadata are not logged.
