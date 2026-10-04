# Live queue feedback

Queue admission remains automatic. To request feedback while an operation waits,
generate a fresh UUID in the caller and include it in the original request:

```http
POST /v1
Content-Type: application/json

{"requestId":"42bb38ee-282a-447f-b4ed-83f55e8e0558","url":"https://target.example/page"}
```

Keep that HTTP request open. A separate feedback request uses the same ID:

```http
GET /queue/42bb38ee-282a-447f-b4ed-83f55e8e0558
```

Example response:

```json
{
  "requestId": "42bb38ee-282a-447f-b4ed-83f55e8e0558",
  "state": "queued",
  "position": 3,
  "total": 5,
  "queueLimit": 16
}
```

Display `position/total` while `state` is `queued`. These values are calculated
for each feedback request, so they reflect departures and arrivals since the
previous check. `total` counts waiting requests, excluding the active browser.
An active request reports `state: "active"`, `position: 0`; this includes browser
startup and cleanup. The pending bound remains 16 by default.

Feedback launches no browser, returns no target URL/private output, and uses
`Cache-Control: no-store`. An unknown, completed, cancelled or rejected request
returns 404 (`Request not tracked`); this is not proof that it succeeded. The
original request carries its result. No completion history is retained.

Successful `/v1` responses include `requestId`; validated responses also carry
`X-Request-ID`, including a duplicate-ID 409 or full-queue 503. IDs must be unique
among active/waiting requests. Reusing a live ID returns 409 without a second
browser submission. Generate a new ID for each new operation, and never resend
an operation merely to obtain feedback.

For callers that omit `requestId`, Byparr generates a UUID automatically. To know
the ID before the response arrives, supply it yourself. No opt-in queue flag,
streaming protocol, persistent session or server timer is introduced.

See [specification and verification](queue-feedback-spec.md). Original endpoint:
`https://media-apps-minipc.tail94fa2c.ts.net:8191`.
