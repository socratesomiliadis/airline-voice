# Architecture

## Process boundaries

The API owns flight search and customer booking operations. REST routes and
ElevenLabs webhook-tool routes share the typed `BookingOperations` boundary and
request-scoped booking service. The service coordinates SQLAlchemy transactions;
policy calculations live in a separate catalog loaded from the JSON knowledge
base. Other feature routers continue to return `501`.

The refiner is a separate Python process. It depends on shared contracts and will
communicate with the API through an adapter. It does not import API internals or
write directly to the API's database. A future isolated workspace adapter owns
candidate changes and verification, separate from customer-facing operations.

The dashboard contains presentation components and monitoring view definitions.
A future server-side API adapter will load data; a dedicated event-stream adapter
will supply live updates. Neither exists yet. Navigation and empty states are the
only current UI behavior.

`packages/contracts` is a leaf dependency shared by Python apps. It contains a
generic JSON payload type, a proposed event envelope, and event transport ports.
It has no dependency on application or provider packages. TypeScript currently
mirrors the small event envelope manually. Generate client types from OpenAPI
when concrete domain schemas are introduced.

## Feature ownership

| Module | Responsibility |
| --- | --- |
| bookings | Flight search, booking, cancellation, rescheduling, and booking items |
| baggage | Baggage policies and tracking inquiries |
| support | Other customer requests and escalation |
| conversations | Conversation metadata, transcripts, and tool activity |
| voice | Implemented booking webhook tools; future voice sessions and call events |
| knowledge | Document ingestion, metadata, retrieval, and search |
| monitoring | Durable monitoring events and a real-time transport |
| refinement | Run control, iteration history, evaluations, and change records |

Each feature starts with `router.py` and `ports.py`. Add domain types, request
schemas, use cases, and repositories to their owning module as real requirements
are implemented. Bookings use typed schemas and a typed application protocol;
other modules still have provisional `JsonObject` boundaries.

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

Knowledge ingestion and search are separate ports so storage and retrieval can
evolve independently. No embedding model, vector index, chunking algorithm,
document parser, or external knowledge provider has been selected. The ignored
`knowledge/sources/` directory is only a local staging area.

`knowledge/` contains one JSON file per fictional development policy: pets,
baggage, accessibility, check-in, cancellations and refunds, and flight changes.
Each file includes metadata, stable rule IDs, plain-language answers, and
structured details. The API loads policy details at startup and persists a policy
snapshot on each booking. Baggage fees, fare-change rules, disruption handling,
and cancellation outcomes use that snapshot. Semantic retrieval and ElevenLabs
knowledge uploads are not implemented.

All money is integer cents in a simulated ledger; no payment processor is called.
Refunds use stored paid amounts. Basic/standard unused-tax and credit settlements
that require an unavailable tax breakdown are recorded for review. Special-item
requests requiring provider acceptance remain `pending_confirmation` and are not
charged. The optional `SIMULATION_NOW` business clock keeps the fixed fixture week
usable; event audit timestamps use real UTC time.

## Refinement extension points

The proposed pipeline has separate protocols for:

1. Simulating customer conversations.
2. Evaluating transcripts and tool outcomes.
3. Diagnosing prompt or code failures.
4. Proposing prompt or code changes.
5. Applying candidate changes in an isolated workspace.
6. Verifying candidates with regression checks and fresh evaluations.
7. Deciding whether quality thresholds require another iteration.

The runner is a protocol, not an implementation. Stage order, inputs and outputs,
artifact formats, scheduling, quality thresholds, iteration limits, retries,
rollback, prompt deployment, and mutation policy remain undefined. Current stage
protocols share a minimal frozen context; replace it with typed stage results
when implementing the pipeline.

## Events and monitoring

The proposed event envelope includes an explicit ID, name, timestamp, correlation
ID, and JSON payload. Publishing, persistence, delivery semantics, replay,
subscriber authentication, and event names are deferred. The `/monitoring/events`
route returns `501`; no SSE or WebSocket connection is opened. Select the transport
when its durability and scaling requirements are known.

## Current runtime guarantees

- API startup creates a lazy engine but performs no database queries or schema writes.
- The liveness endpoint reports process availability only.
- Flight and booking operations persist to PostgreSQL; unrelated platform routes return `501`.
- The worker CLI cannot run simulations or modify prompts or code.
- Dashboard views contain no fabricated operational data or automated network calls.
- Provider adapters contain no SDK calls; credentials are confined to backend settings.

The implementation follows the documented [FastAPI router composition](https://fastapi.tiangolo.com/tutorial/bigger-applications/),
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/),
[Next.js App Router](https://nextjs.org/docs/app/getting-started/installation), and
[Tailwind PostCSS](https://tailwindcss.com/docs/installation/framework-guides/nextjs)
setup patterns.
