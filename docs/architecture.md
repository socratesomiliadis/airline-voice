# Architecture

## Process boundaries

The API is the future owner of customer operations, conversation records,
knowledge access, and monitoring data. Its HTTP layer delegates to feature modules;
feature modules define application ports; infrastructure adapters implement ports.
Routers currently stop at a shared `501` placeholder.

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

| Module | Future responsibility |
| --- | --- |
| bookings | Booking, cancellation, rescheduling; airline provider integration |
| baggage | Baggage policies and tracking inquiries |
| support | Other customer requests and escalation |
| conversations | Conversation metadata, transcripts, and tool activity |
| voice | ElevenLabs sessions, webhook verification, and tool dispatch |
| knowledge | Document ingestion, metadata, retrieval, and search |
| monitoring | Durable monitoring events and a real-time transport |
| refinement | Run control, iteration history, evaluations, and change records |

Each feature starts with `router.py` and `ports.py`. Add domain types, request
schemas, use cases, and repositories to their owning module as real requirements
are implemented. `JsonObject` in ports is a temporary payload boundary, not a
final domain schema.

## Persistence and knowledge

PostgreSQL is the persistent database. SQLAlchemy provides async engine/session
plumbing, and Alembic provides migration configuration. No domain tables exist.
Session dependencies close sessions without implicitly committing transactions;
transaction ownership is a future application-layer decision.

Knowledge ingestion and search are separate ports so storage and retrieval can
evolve independently. No embedding model, vector index, chunking algorithm,
document parser, or external knowledge provider has been selected. The ignored
`knowledge/sources/` directory is only a local staging area.

`knowledge/` contains one JSON file per fictional development policy: pets,
baggage, accessibility, check-in, cancellations and refunds, and flight changes.
Each file includes metadata, stable rule IDs, plain-language answers, and
structured details. No runtime loader, retrieval implementation, or ElevenLabs
upload is connected to these files yet.

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
- All customer, provider, knowledge, and refinement routes return `501`.
- The worker CLI cannot run simulations or modify prompts or code.
- Dashboard views contain no fabricated operational data or automated network calls.
- Provider adapters contain no SDK calls; credentials are confined to backend settings.

The implementation follows the documented [FastAPI router composition](https://fastapi.tiangolo.com/tutorial/bigger-applications/),
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/),
[Next.js App Router](https://nextjs.org/docs/app/getting-started/installation), and
[Tailwind PostCSS](https://tailwindcss.com/docs/installation/framework-guides/nextjs)
setup patterns.
