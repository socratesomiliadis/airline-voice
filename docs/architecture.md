# Architecture

## Process boundaries

The API owns flight search and customer booking operations. REST routes and
ElevenLabs webhook-tool routes share the typed `BookingOperations` boundary and
request-scoped booking service. The service coordinates SQLAlchemy transactions;
policy calculations live in a separate catalog loaded from the JSON knowledge
base.

The refiner is a separate Python process using REST and Chat Mode adapters.
It does not import API internals or write directly to the API's database. Its
workspace adapter applies bounded backend edits, verifies them, reloads the
service and restores failed changes. See [autonomous refinement](refinement.md).

The dashboard observes the worker through a server-side GET-only proxy. The API
reads redacted worker snapshots from a shared artifacts directory and streams
server-sent events. A client provider handles reconnects, transport heartbeats and
selection across views. Conversations, scores, changes and history update without
manual commands. See [observation architecture](monitoring.md).

`packages/contracts` is a leaf dependency shared by Python apps. Its concrete
observation contracts in `monitoring.py` describe run summaries, iterations,
conversations, and snapshots. The dashboard mirrors these contracts manually in
`src/lib/api/contracts.ts`; keep the two definitions aligned when payloads change.
It has no dependency on application or provider packages.

## Feature ownership

| Module | Responsibility |
| --- | --- |
| bookings | Flight search, booking, cancellation, rescheduling, and booking items |
| voice | Authenticated ElevenLabs webhook tools and their portable contracts |
| monitoring | Durable observation snapshots and a real-time transport |

Feature modules contain their implemented routes, schemas, services, and adapters.
Bookings use typed schemas and a typed application protocol shared by REST and
webhook routes. The separate refiner application owns simulation, evaluation,
repair, and iteration history. Policy data lives in `knowledge/`.

## Persistence and knowledge

PostgreSQL is the persistent database. SQLAlchemy provides async engine/session
plumbing, and Alembic provides schema migrations. The flight database has `airports`,
`flights`, `flight_cabins`, and `flight_fares` tables. Cabin inventory is shared
across its fare tiers, and prices are stored in integer USD cents.

`bookings` records fare and price snapshots, policy snapshots, timestamps, status,
and a unique reference. `booking_passengers` retains passenger identities;
`passenger_reservations` enforces one active allocation per passenger and flight.
`booking_extras`, `booking_events`, and `api_operations` retain items, financial
simulation/audit history, and successful idempotency responses.

Mutations commit one transaction containing inventory, passenger allocations,
booking state, extras/events, and the idempotency receipt. A receipt insert and row
lock serialize retries. Reusing a key with different input returns `409`.
Booking row locks serialize cancellation, rescheduling, and baggage additions.
Flight and cabin rows are locked in sorted order so opposite reschedules use the
same lock order. Availability is checked while locked; failed operations roll back
both original and target inventory. Cancellation removes active allocations once
and retains historical booking/passenger records.

No booking state is held in a process-local collection. A subsequent caller or new
application instance reads the same committed PostgreSQL records. Session
dependencies close sessions; the application service owns transaction commits.

`data/flights/week_2026_11_09.json` seeds 112 fictional flights departing November
9–15, 2026, with three cabin classes and six fare offers per flight. The explicit
seed command validates the data and inserts missing rows without replacing existing
inventory, flight status, or fares. This JSON is reproducible seed input; the mutable
PostgreSQL tables are the booking API's flight inventory source. See the
[flight database guide](../data/flights/README.md) for setup and query examples.

ElevenLabs manages policy retrieval for the assistant.

`knowledge/` contains one JSON file per fictional development policy: pets,
baggage, accessibility, check-in, cancellations and refunds, and flight changes.
Each file includes metadata, stable rule IDs, plain-language answers, and
structured details. The API loads policy details at startup and persists a policy
snapshot on each booking. Baggage fees, fare-change rules, disruption handling,
and cancellation outcomes use that snapshot. The provisioning script uploads the
six policies to ElevenLabs for provider-managed retrieval during calls. Rerun
provisioning after changing policy documents.

All money is integer cents in a simulated ledger; no payment processor is called.
Refunds use stored paid amounts. Basic/standard unused-tax and credit settlements
that require an unavailable tax breakdown are recorded for review. Special-item
requests requiring provider acceptance remain `pending_confirmation` and are not
charged. The optional `SIMULATION_NOW` business clock keeps the fixed fixture week
usable; event audit timestamps use real UTC time.

## Autonomous refinement

The concrete runner evaluates every scenario in each iteration. Separate stages
simulate an LLM customer over ElevenLabs Chat Mode, judge the transcript and tool
results with per-failure prompt/code diagnosis, and propose both kinds of repair.
Pydantic contracts validate scenarios, scores, evidence quotes and patch payloads.
Workspace adapters apply exact replacements, compile/test changes, reload the
existing service and roll back failed repairs. Changed prompts publish through
ElevenLabs REST. Every criterion must reach the configurable threshold (8/10 by
default); the loop allows 5 evaluated iterations by default. Artifacts contain
full evidence and repair histories. No final untested repair is deployed.

See [configuration, lifecycle and failure recovery](refinement.md). The executable
entry point is the host CLI. HTTP monitoring routes provide observation only.

## Events and monitoring

The worker publishes durable, redacted `monitor.json` snapshots as conversations
and stages progress. Shared Pydantic observation contracts live in
`packages/contracts`. The authenticated monitoring API exposes snapshots and
server-sent events; it does not write to the worker or run it. Full snapshots make
reconnect and replay idempotent across API reloads. The dashboard proxies the
stream with server-only credentials. Worker and transport heartbeats are separate,
and the viewer shows stale/disconnected state without inventing activity.

Monitoring uses the concrete observation contracts described in
[the monitoring guide](monitoring.md).

## Current runtime guarantees

- API startup creates a lazy engine but performs no database queries or schema writes.
- The liveness endpoint reports process availability only.
- Flight and booking operations persist to PostgreSQL; only implemented routes are registered.
- The worker CLI autonomously simulates, evaluates, patches and redeploys within configured limits.
- Dashboard views contain only recorded observations and accept no loop-control commands.
- Provider credentials stay in server-side settings; artifacts redact known secret values.

The implementation follows the documented [FastAPI router composition](https://fastapi.tiangolo.com/tutorial/bigger-applications/),
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/),
[Next.js App Router](https://nextjs.org/docs/app/getting-started/installation), and
[Tailwind PostCSS](https://tailwindcss.com/docs/installation/framework-guides/nextjs)
setup patterns.
