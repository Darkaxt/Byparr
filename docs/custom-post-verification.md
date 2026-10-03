# Custom POST verification — 2026-10-03

| Contract | Inspected evidence |
| --- | --- |
| Validation before browser creation | Focused offline API/model checks reject unsupported commands, POST options on GET, oversized UTF-8 bodies, foreign preflight origins and invalid/browser-owned headers |
| Browser-network POST | Real browser fixture receives exact form and JSON strings, including UTF-8, expected content type and matching user agent |
| Redirects | Real 303, 307 and 308 fixtures verify final method/body; cross-origin cases verify Authorization stripping and body-header handling |
| Response fidelity | Fixture 422/503 statuses returned in `solution.status`, raw JSON retained, GET regression passed; cookies-only and POST PDF-without-GET-refetch checked offline |
| Challenge replay contract | Real browser detects and clears a deterministic fixture interstitial; default returns 409 with one POST, permission returns 200 with exactly two POSTs; repeated-challenge limit checked offline |
| Admission and lifecycle | Actual deployed HTTP API returns immediate 429 for excess work, `/ready` stays available, sequential calls succeed; offline launch-failure/cancellation checks and ASGI cleanup-before-response regression pass |
| Deployment constraints | Docker inspect confirms private loopback 8192, 0.5 CPU, 1 GiB memory/swap equality, 256 PIDs, bounded tmpfs/logs, non-root/read-only/capability/security settings, no restart or browser health check |
| Controlled resource use | Fresh complete browser fixture run: `memory.peak=958279680` bytes (~914 MiB), `pids.peak=240`, zero OOM or memory/PID-limit events |
| External POST | Real `https://httpbin.org/post` returned API 200/target 200 and correctly decoded the harmless UTF-8 form field |
| External challenge limitation | `https://1337x.to/home/` detected a challenge and returned API 408. The broader sequence recorded one bounded browser OOM and PID-limit events; API recovered. Site-specific Cloudflare POST clearance remains unverified |
| Production preservation | Byparr stays healthy, Prowlarr stays running; container identities/images/start times/restart counts, production Compose SHA-256 and Tailscale Serve SHA-256 match the preflight baseline |

Offline verification command (requires the test dependency group, Python 3.14):

```sh
python -m pytest tests/admission_test.py tests/post_test.py tests/main_test.py tests/owui_test.py -k 'not bypass and not json_api and not health_check and not pdf_handling and not test_owui_load_basic and not test_owui_load_multiple_urls and not test_owui_load_invalid_url_graceful and not test_owui_load_accepts_valid_key' -q --tb=short -p no:cacheprovider
ruff check src tests runtime tools
git diff --check
```

The excluded inherited tests launch browsers against public websites. They were
not run as a broad live suite; real browser, deployed API and external checks
above provide the required scoped integration evidence. The local locked test
environment and the reused deployed runtime have different dependency revisions;
the actual deployed runtime received real-browser and HTTP API verification.

Private raw deployment, baseline, comparison, external and stopped-state evidence
is retained in `/opt/byparr-custom` and local ignored `local-evidence/`.
Portable source/configuration and this summary are maintained in the fork.

The stopped test image shares its large immutable runtime layers with production;
Docker reports only 221.3 kB unique image data. The unused validation image and
787.3 kB of private task build cache were removed using reviewed exact IDs.
Shared references belonging to the retained images and pre-existing build cache
remain. No broad Docker prune, production cleanup or extra runtime download ran.
