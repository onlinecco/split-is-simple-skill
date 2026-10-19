# Split Is Simple public API v1

Base URL: `https://splitissimple.com`. Anonymous: no account or API key.
The full, case-sensitive event ID is a bearer capability: anyone with its link can read, edit or delete the event. Keep it out of public examples, telemetry and issue reports.

These are two resource endpoints: creation at `/api/v1/events`, and reading/updating an event at `/api/v1/events/{id}`. These are REST/JSON APIs, not an MCP server. An MCP-capable client may wrap the same schemas as tools.

## Create

`POST /api/v1/events`

Headers:
- `Content-Type: application/json`
- `Idempotency-Key: <random UUID or 16–128 character random base64url string>`

Generate a fresh key for each intended event. Reuse exactly the same key and body after a timeout or transient failure. Keep keys confidential; they can recover the event link. Identical retries return the existing event, including its latest state. Reusing a key for a different normalized creation payload returns 409. Retry metadata is retained for at least 24 hours, with opportunistic bounded cleanup. Never intentionally reuse an old key for a new event. Rotating the server idempotency secret ends the retry guarantee, but does not invalidate existing links.

```json
{
  "name": "Weekend trip",
  "mode": "group",
  "currency": "USD",
  "participants": [
    {"id": "alex", "name": "Alex", "group": "alex-sam"},
    {"id": "sam", "name": "Sam", "group": "alex-sam"},
    {"id": "blair", "name": "Blair"}
  ],
  "expenses": [
    {"id": "dinner-1", "title": "Dinner", "amount": 90, "paidBy": "alex", "included": ["alex", "sam", "blair"]}
  ]
}
```

`name` and `participants` are required. `expenses` defaults to `[]`. `mode` defaults to `group`; `individual` is also supported. `currency` defaults to `USD`; all other currencies are rejected. The server assigns participant colors and internal event IDs.

Participant `group` is an optional household key (1–94 characters). Give members of the same household the same key. Omitted or null on creation means a separate household for that person. Names are display values; use distinct IDs even for people with identical names. Group mode aggregates household balances; each expense is still divided equally among the people in `included`, not equally among households. Unequal shares, multiple payers within one expense and currency conversion are not supported.

Amounts are positive USD numbers with at most two decimal places, no more than 1,000,000,000. `paidBy` and every `included` entry must reference existing participant IDs. `included` must be nonempty and contain no duplicates. IDs use 1–80 ASCII letters, numbers, `_` or `-`. Participant names: 1–100 characters; event names: at most 200; expense titles: 1–200. Each event allows at most 20 participants and 100 expenses. JSON bodies are limited to 250,000 bytes; images are not accepted.

Returns 201, including on identical retries:

```json
{
  "id": "<22-character secret>",
  "url": "https://splitissimple.com/?event=<22-character secret>",
  "revision": 1,
  "updatedAt": "<ISO timestamp>",
  "mode": "group",
  "currency": "USD",
  "event": {
    "id": "event-1",
    "name": "Weekend trip",
    "participants": [],
    "expenses": []
  }
}
```

The response `event` contains the actual participants and expenses (arrays abbreviated above). Participant group values are household keys or null. Response headers include an ETag, `Location`, and `Cache-Control: private, no-store`. Hosting compression may weaken the response ETag (for example `W/"1"`); build update preconditions from the JSON `revision` rather than copying that header.

## Read before an update

`GET /api/v1/events/{id}` returns the same response shape and an ETag. Use its JSON `revision` to construct a strong `If-Match` value, such as `"1"`; do not forward a weak hosting ETag. Read immediately before planning an update. Preserve IDs; do not match by name alone. The ID is the `event` query value from the user-supplied link, not `event.id` in the JSON response.

## Update

`PATCH /api/v1/events/{id}`

Headers: `Content-Type: application/json`, `If-Match: "<revision from last read>"`.

```json
{
  "expenses": [
    {"id": "taxi-1", "title": "Taxi", "amount": 24, "paidBy": "blair", "included": ["alex", "sam", "blair"]}
  ]
}
```

Omitted event fields and omitted records are preserved. `participants` and `expenses` are ID-based upserts: a new ID adds a record, an existing ID updates it. Supply the full expense record when editing an expense; for a participant supply `id` and `name`, plus `group` only when changing household. Omitted participant `group` preserves its existing group. Explicit null separates that participant into their own household. Omitted `mode` preserves the current mode. `name` updates the event title.

Use `removeExpenseIds` / `removeParticipantIds` arrays only for explicit user-requested deletion. Removing a participant fails if a remaining expense references them. Correct or remove those expenses in the same patch, or beforehand. Never remove and upsert the same ID in one request. On older books containing several events, only the active event is changed; other events are preserved.

Returns 200 with the complete latest event, URL and incremented revision. Missing If-Match returns 428; stale revisions return 412 without any changes. On a 412, read again. Automatically reconcile independent additions and already-applied identical changes; ask before resolving competing edits to the same record. Do not blindly repeat a stale patch with a new revision. Updates never create missing/deleted events.

## Limits and errors

No login, API key or browser CAPTCHA is required. Existing website and API traffic share IP budgets: creation 5 attempts/minute and 20/hour; reads 240/minute; writes 300/minute per IP and per event. These are abuse safeguards, not guaranteed capacity or per-person quotas. Forwarded IP headers are trusted only on Vercel. On an unconfigured/local host all callers share a fallback bucket. Raw IPs are not persisted in these counters. Server-to-server clients omit browser Origin headers; cross-site browser writes are rejected. No permissive CORS policy is provided.

Errors are JSON `{ "error": "..." }`: 400 invalid input/key/revision; 403 cross-site request; 404 unknown link; 409 creation-key conflict; 410 retry of a deleted event during the retry window; 412 stale revision; 413 body too large; 415 media type/encoding; 428 missing revision; 429 rate limited (`Retry-After` seconds); 503 temporary outage. Unknown JSON fields are rejected.

After a create timeout/503, retry with the same key and body. After an update timeout, GET and compare affected records before deciding whether to retry. Respect Retry-After; do not retry validation errors. Retry at most twice automatically, then report the error. Do not claim success or invent an event URL without a confirmed API response.

## Deployment

The routes ship with the existing Next.js application; there is no separate API service. Configure the existing DATABASE_URL and a stable API_IDEMPOTENCY_SECRET (or RATE_LIMIT_SECRET fallback). Apply the generated Drizzle migration with the other migrations, or allow the existing runtime schema bootstrap role to create the new api_event_creations table. A role without DDL privileges requires the migration before traffic reaches the API.

Receipt extraction happens in the user's LLM client; the API receives structured event data only. No receipt files or new model credentials are stored by these endpoints. Database/provider logs and backups remain governed by the hosting configuration.
