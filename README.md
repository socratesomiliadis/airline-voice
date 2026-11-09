# Airline Voice

Airline Voice is an assessment prototype for an airline customer service agent.
ElevenLabs runs the airline assistant. FastAPI provides the application programming interface (API). PostgreSQL stores bookings and inventory.
A Python worker tests conversations and repairs prompts or backend functions. A Next.js dashboard shows the results.

All airline policies, flights, customers, and financial movements are fictional.
The refinement loop uses text conversations. It does not require audio or human approval between iterations.

This README records the current design, its reasons, its costs, and the limits of the available evidence.
Earlier project discussions informed these decisions. The current code and linked reports establish their implementation status.

[Scope](#current-scope) · [Decisions](#design-decisions-and-tradeoffs) · [Setup](#local-setup) · [Verification](#verification) · [Evidence](#recorded-evidence-and-its-limits)

## Current scope

| Area | Implemented behavior | Limit |
| --- | --- | --- |
| Flights | Search by route, local date or date range, price, cabin, and fare tier. Retrieve gates and flight status. | The schedule and operational data are fictional. |
| Bookings | Create, retrieve, cancel, and reschedule bookings. Add baggage and special-item requests. Save passenger seat preferences. | Payments are simulated. Seat preferences are requests, not assigned seats. |
| Persistence | Share committed bookings and inventory across callers and API restarts. | Caller identity and booking ownership still need production authorization. |
| Policies | Load six JSON policies in the API and attach them to ElevenLabs for retrieval. | Local document ingestion and knowledge-search routes remain unimplemented. |
| Refinement | Simulate, score, diagnose, repair, verify, reload, and repeat automatically. | Generated code executes with the worker's host permissions. |
| Monitoring | Show live conversations, tool activity, scores, diagnoses, changes, and history. | The dashboard can observe runs but cannot control them. |

Seven ElevenLabs tools and seventeen executable scenarios cover all ten assessment call types.
Reserved support, conversation-storage, voice-session, knowledge, and refinement-control routes return `501 Not Implemented`.
Their presence does not mean those platform features work. See the [API reference](docs/api.md) and [scenario coverage](scenarios/README.md).

## Design decisions and tradeoffs

The requested stack includes ElevenLabs, FastAPI, a persistent database, Python refinement, Docker Compose, and Next.js.
The requested interface permits observation only. The requested repair scope permits targeted function changes, without arbitrary refactoring.

PostgreSQL, SQLAlchemy, Alembic, uv, and the other tools below are implementation choices.
They are not additional assessment requirements. Tailwind and SVG icons follow the repository instructions.
Shadcn with Base UI and Anthropic model calls follow later explicit project decisions.

### Application structure and tools

| Decision | Reason | Cost or limit |
| --- | --- | --- |
| Separate API, worker, and dashboard processes in one repository. | Each process has one runtime responsibility. The worker can restart the API while monitoring remains available. | Local execution needs several processes and shared configuration. |
| Use feature modules, typed ports, and infrastructure adapters. | REST and webhook routes share booking logic. Provider and filesystem operations stay outside pipeline stages. | Some unused interfaces remain as documented extension points. They are scaffolding, not completed features. |
| Use PostgreSQL 17, async SQLAlchemy, and asyncpg. | Transactions, constraints, and row locks protect shared inventory and persistent bookings. | Development and meaningful backend verification need PostgreSQL. |
| Use Alembic for versioned schema changes. | Schema updates are explicit and reviewable. | Operators must apply migrations. Startup does not migrate or seed the database. |
| Use Python 3.12+, uv workspaces, and Hatchling packaging. | Python applications share dependency resolution and installable package boundaries. | Contributors need uv and must preserve `uv.lock`. |
| Use Pydantic for settings and payload validation. | Typed contracts reject malformed requests and model output. | Valid structure alone does not establish correct behavior. Evidence checks remain necessary. |
| Use Next.js App Router, TypeScript, npm, and Biome. | The dashboard has typed views, server routes, and consistent source checks. | JavaScript dependencies and `package-lock.json` need separate maintenance. |
| Use GitHub Actions for continuous integration (CI), plus Docker builds. | CI repeats source checks, database verification, and image builds. | Passing CI does not establish provider availability or conversational quality. |

### Booking, policy, and time rules

| Decision | Reason | Cost or limit |
| --- | --- | --- |
| Use mutable PostgreSQL inventory; keep JSON as seed input. | Booking changes remain visible across calls and restarts. | Reimporting the dataset preserves existing prices and inventory. It does not reset an experiment. |
| Share inventory between fare tiers in each cabin. | Several prices for one cabin must not create extra seats. | Cabin class and fare tier are separate concepts. Policies use the fare tier. |
| Commit inventory, booking state, passenger allocations, audit events, and retry receipts together. | A failed operation must not leave partial changes. | Concurrent requests can wait for database locks. |
| Lock inventory rows in a consistent order. | Opposite reschedules use the same lock order. This reduces deadlock risk. | Transaction and concurrency tests remain essential. |
| Require mutation idempotency keys and active passenger/flight uniqueness. | Retries must not repeat purchases or allocate the same passenger twice on one flight. | A retry must retain its key and exact input. Changed input with the same key returns `409`. |
| Store money as integer USD cents and retain paid-price snapshots. | Calculations avoid floating-point money errors. Refunds use the recorded purchase amount. | No payment processor executes charges or refunds. Some settlements require manual review. |
| Keep one JSON file per policy, with stable rule IDs and structured amounts. | People can edit each policy separately. The API can calculate fees from the same policy content. | Policy edits require API reload and ElevenLabs synchronization. No local vector index or embedding model is selected. |
| Save a policy snapshot with each booking. | Later policy edits must not silently change an existing booking's terms. | Existing bookings retain their original rules. |
| Return airport-local times and timezone names explicitly. | The assistant must not describe a UTC timestamp as local time. | Date searches use the departure airport's local calendar date. |
| Separate the business clock from audit time. | `SIMULATION_NOW` keeps the fixed sample week usable. Audit events retain actual UTC timestamps. | Demonstrations need a consistent business clock across fixtures and evaluation. |

Register all physical bags, including included bags. The backend applies the fare allowance.
Registering only additional bags can produce the wrong fee.
Restricted-item requests can remain `pending_confirmation`, without a charge.
Available passenger seats do not establish pet capacity or special-assistance acceptance.

See [booking semantics](docs/api.md), [policy content](knowledge/README.md), and [flight data](data/flights/README.md).

### Refinement and evaluation

An iteration is one evaluation cycle. A fixture is fictional test data, including any prerequisite booking.
An idempotency receipt is the stored result of a successful keyed request.
The independent reference calculation is the fixture oracle.

The worker performs this cycle:

1. Create fresh caller and action identifiers. Prepare prerequisite bookings and calculate selection references before each conversation.
2. Simulate customers through ElevenLabs Chat Mode. Retrieve the authoritative transcript and tool results.
3. Save booking state before cleanup. Release fixture inventory while retaining audit history.
4. Score understanding, API correctness, outcome confirmation, and naturalness from 1–10. Run deterministic outcome and policy checks.
5. Diagnose failures. Propose a prompt rewrite, a bounded backend repair, or both when the evidence supports those changes.
6. Verify backend repairs, reload the API, and confirm readiness. Publish changed prompts and repeat the suite.

Every criterion in every scenario must reach at least **8/10**, and all deterministic checks must pass.
The default limit is **5 evaluated iterations**, including the baseline.
A high average cannot hide one failed criterion. The worker does not deploy an unevaluated repair after the final iteration.
TOML settings and command-line interface (CLI) options can change both limits.

| Decision | Reason | Cost or limit |
| --- | --- | --- |
| Use Anthropic Messages for customer, evaluator, and repair calls. | The project changed providers after an Anthropic key became available. | OpenAI keys and endpoint overrides no longer configure these calls. ElevenLabs separately runs the assistant. |
| Keep the three model roles separate. | Evaluation uses conversation evidence, without the customer model's hidden reasoning. Each role has separate instructions. | Separate calls can still share model biases. They are not independent human review. |
| Use Haiku for customers and Sonnet for evaluation and repair by default. | The configuration gives the customer and diagnosis roles different model budgets. | These are configurable defaults, not evidence that one model choice is optimal. |
| Combine model scores with deterministic checks. | Saved state and tool results can contradict an optimistic judge. Failed factual checks block a pass. | Language checks cover specific failures. They are not a complete semantic verifier. |
| Calculate earliest/cheapest references from trusted flight JSON, without importing API search logic. | Search and evaluation must not agree on the same implementation defect. All equally optimal offers are valid. | Use a dedicated seeded database without external inventory writers. Inventory drift invalidates the reference assumptions. |
| Require actual failure quotes and exact code locations. | Repairs need evidence and a diagnosed file, function, and faulty behavior. | Invalid or incomplete evidence cannot authorize a repair. |
| Separate reproducible application failures from infrastructure failures. | A broken cancellation endpoint must remain diagnosable when it also breaks cleanup. A tunnel outage needs connection recovery. | Healthy probes do not establish that every endpoint dependency works. Some failures still require investigation. |
| Pause new fixtures when cleanup fails. | Further fixtures would consume inventory and obscure the original problem. | Pending cleanup must succeed before the next iteration. Unresolved cleanup prevents success. |
| Limit edits to diagnosed existing backend functions. | Exact replacements and syntax-tree checks reject unrelated changes, stale source, and arbitrary refactoring. | The default scope excludes tests, scenarios, policies, and the refiner. Scope validation is not an execution sandbox. |
| Require actual PostgreSQL verification before backend activation. | A successful test command can otherwise hide skipped database regressions. | Required tests must run and pass. Missing, skipped, stale, or incomplete verification receipts block activation. |
| Disable API auto-reload during refinement. | Candidate source must pass verification before the running API loads it. | Interactive development uses a separate watched command. The worker refuses watched APIs. |
| Restore source and prompt after failed activation. | Verification, reload, readiness, or publication failures must not silently leave an accepted candidate. | Recovery is best effort within the running process. Failed recovery stops the run with an error. |
| Send repair evidence for actionable failed scenarios only. | Full-suite transcripts, debug events, and duplicate dialogue previously exceeded the model context limit. | Complete evidence stays in artifacts. The reduced request does not eliminate model limits. |

Reads and keyed mutations can receive bounded retries. Arbitrary writes are not replayed.
A repeatable endpoint failure requires matching 5xx responses plus successful health and authenticated database-readiness probes.
Missing conversations remain missing; the worker does not invent evidence to continue.

See the [refinement guide](docs/refinement.md) for retry rules, patch validation, cleanup recovery, and deployment semantics.

### Dashboard and observation transport

The dashboard has three views: **Overview**, **Conversations**, and **Evaluations**.
Changes and iteration history are tabs within Evaluations. This replaces repeated screens with distinct inspection tasks.
Run, iteration, scenario, and filter controls change the displayed data only.

| Decision | Reason | Cost or limit |
| --- | --- | --- |
| Use CLI-installed shadcn components with Base UI, Tailwind, and Lucide SVG icons. | Composable components provide consistent controls and interaction behavior. | Add components with the shadcn CLI. Retain shared theme variables for future components. |
| Use a small SVG score chart. | The required trend does not need the removed Recharts dependency. | More complex charts would need additional implementation. |
| Publish redacted file snapshots and stream complete snapshots through server-sent events (SSE). | Monitoring survives API restarts and reconnects without an in-memory event queue. | The API polls artifact revisions. This design targets a local assessment, not large-scale event distribution. |
| Keep the API key in a server-side, GET-only dashboard proxy. | Browser code receives observations without receiving the integration secret. | The proxy does not authenticate the viewer. Public deployment needs separate access control. |
| Separate worker and transport heartbeats. | An open connection must not make an abandoned worker look active. | Reconnect and stale warnings report observations; they do not repair the worker. |
| Display only actual recorded data. | Empty and partial runs must not acquire invented conversations, scores, or improvement claims. | Missing evaluations remain pending or null. Historical reports can lack newer evidence fields. |

The trend shows each criterion's lowest scenario score. Historical selection stays selected while live work continues.
Completed transcripts open at the beginning. Live transcripts follow messages until the viewer scrolls away.
See [monitoring behavior and setup](docs/monitoring.md).

## Local setup

### Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Node.js 22+ and npm.
- Docker with Compose for PostgreSQL or the application stack.
- `lsof` for development-server port guards.
- An ElevenLabs account and Anthropic credentials for live refinement.
- A public HTTPS endpoint for ElevenLabs to reach the local booking API.

Run commands from the repository root. Before starting a server, examine existing listeners:

```sh
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:3000 -sTCP:LISTEN
docker compose ps
```

Reuse existing project services. Local and Compose applications use the same default ports.
Copy configuration files only when they do not already exist:

```sh
cp -n .env.example .env
cp -n apps/dashboard/.env.example apps/dashboard/.env.local
make setup
docker compose up -d database
make migrate
make seed-flights
```

The seed contains 112 flights across seven airports for November 9–15, 2026.
It includes three cabin classes and six fare offers per flight.
Repeated imports preserve existing data. Migrations and seeds never run during API startup.

Start each application in a separate terminal, if its port is free:

```sh
make dev-api
```

```sh
make dev-dashboard
```

- Dashboard: <http://localhost:3000>
- API documentation: <http://localhost:8000/docs>
- Process liveness: <http://localhost:8000/health>
- Authenticated database readiness: <http://localhost:8000/ready>

Liveness does not establish database, public tunnel, or provider readiness.
Use `make dev-api-watch` for interactive editing only. Use `make dev-api` for refinement.

### Provider setup and first refinement

Set credentials and the public HTTPS origin in the root `.env` file.
Follow [first-time ElevenLabs setup](docs/elevenlabs.md) to create your own private agent:

```sh
uv run --all-packages python scripts/configure_elevenlabs.py --create-agent "Airline assessment"
```

Save the printed agent ID as `ELEVENLABS_AGENT_ID`.
The script configures six policies, seven tools, the system prompt, and secret-header authentication.
Account-specific manifests stay under ignored `.local/elevenlabs/`; the repository supplies no account resource IDs.
Provisioning can resume from those manifests. Existing agents retain their voice and model.

Temporary tunnel URLs change. Update `PUBLIC_API_BASE_URL` and rerun provisioning when the URL changes.
Localhost working does not mean ElevenLabs can reach it.
CLI refinement tests the public endpoint before model calls when that origin is configured.

Run the worker on the host:

```sh
make refine
```

The target adds `.tools/bin` to subprocess `PATH`. The dashboard populates automatically from the shared artifacts directory.
Override the quality or iteration limit when necessary:

```sh
uv run --package airline-refiner airline-refiner run \
  --config config/refinement.example.toml --pass-score 9 --max-iterations 3
```

Exit codes are `0` for success, `1` for iteration exhaustion, and `2` for configuration or execution errors.
An unavailable agent can indicate exhausted ElevenLabs credits. A previous incident exposed this cause only in provider Preview.
Do not treat that provider message as proof of a prompt or booking defect.

### Configuration reference

| Setting | Purpose |
| --- | --- |
| `DATABASE_URL` | API database connection. Compose uses the `database` hostname instead of `localhost`. |
| `TEST_DATABASE_URL` | PostgreSQL verification connection. The role needs `CREATE DATABASE` for disposable test databases. |
| `AGENT_API_KEY` | Shared integration secret. ElevenLabs sends the same value through `X-Agent-Api-Key`. |
| `ELEVENLABS_API_KEY` | Provisioning and worker access to ElevenLabs. The booking API does not need this key. |
| `ELEVENLABS_AGENT_ID` | Your configured assistant. TOML can optionally select an isolated agent branch. |
| `ANTHROPIC_API_KEY` | Model credential. `REFINER_MODEL_API_KEY` is the fallback when this value is absent. |
| `REFINER_MODEL_BASE_URL` | Anthropic Messages endpoint. Custom endpoints must implement that contract. |
| `PUBLIC_API_BASE_URL` | Public HTTPS origin used by ElevenLabs tools and worker preflight. |
| `REFINER_API_BASE_URL` | Worker connection to the booking API. Default: `http://localhost:8000`. |
| `REFINER_CONFIG_PATH` | Worker TOML configuration. Default: `config/refinement.example.toml`. |
| `REFINER_ARTIFACTS_DIR` | Shared worker/API observation directory. Default: `artifacts`. |
| `KNOWLEDGE_DIR` | API policy directory. Default: `knowledge`. |
| `SIMULATION_NOW` | Optional timezone-aware business time. The sample configuration uses `2026-11-06T12:00:00Z`. |
| `API_BASE_URL` | Server-side dashboard connection. Local dashboard overrides belong in `apps/dashboard/.env.local`. |

Python settings read root `.env` when commands run from the repository root.
The local dashboard proxy also reads the integration key there. Deployments supply dashboard settings through server environment variables.
Never expose credentials through `NEXT_PUBLIC` variables.

Development/test mode permits requests without an integration key when none is configured.
Production rejects protected requests with `503` until a key is set.
Set the key before exposing a development API publicly.

The [worker configuration](config/refinement.example.toml) defines role-specific models, timeouts, editable paths, verification commands, and reload commands.
Model names in that file are project defaults. Adjust them for your provider access.

## Docker Compose alternative

Compose starts PostgreSQL, the API, and the dashboard. Use this instead of duplicate local application servers:

```sh
cp -n .env.example .env
docker compose up --build
```

For a new database, run these commands in another terminal:

```sh
docker compose run --rm --no-deps api alembic -c apps/api/alembic.ini upgrade head
docker compose run --rm --no-deps api airline-seed-flights
```

Published ports bind to localhost. Named volumes preserve data after `docker compose down`.
The API mounts host `./artifacts` read-only so it can observe the host worker.
Update that mount when using a different artifacts directory.

The optional refiner container supports CLI inspection only:

```sh
docker compose --profile refinement run --rm refiner --help
```

Run autonomous refinement on the host because it must edit source, execute tests, and reload the existing API.
The container's source-asset mounts are read-only; its artifact volume is separate from the host observation directory.

## Verification

```sh
make check
make verify-backend
docker compose config --quiet
```

`make check` runs Python lint, format, type, and test checks, plus dashboard checks and a production build.
Ordinary pytest execution skips database tests without an exported `TEST_DATABASE_URL`.
`make verify-backend` loads root `.env` and requires PostgreSQL verification receipts with all required tests executed successfully.
Its fixtures create and drop disposable databases; they do not reset the application database.
CI uses the strict gate and builds all three application images.

These checks cover inventory races, repeated requests, rollback, persistence, policies, repair controls, and monitoring behavior.
They do not replace live provider runs. Synthetic speech recognition and generated audio have passed earlier smoke tests.
Physical microphone, speaker quality, and real conversational interruption still need hands-on testing.

## Recorded evidence and its limits

| Evidence | What it establishes | What it does not establish |
| --- | --- | --- |
| [Original prompt-repair run](examples/recorded-run/README.md) | Thirteen scenarios passed in two iterations after an automatic prompt repair on an isolated branch. | The starting prompt deliberately withheld booking references. No code repair occurred. Current references and factual checks were absent. One policy explanation received an incorrect passing score. |
| [Backend-repair run](examples/backend-repair-run/README.md) | A real model removed an injected fault in `BookingService._cancel`. Actual PostgreSQL verification, API reload, cleanup recovery, and a fresh cancellation succeeded. | The fault was deliberately inserted. Later interaction failures, a context-limit rejection, and a provider error remain. The run did not pass. |
| [Focused interaction-repair run](examples/interaction-repair-run/README.md) | Four harder scenarios passed after an automatic prompt repair in the second iteration. | The other thirteen scenarios were not rerun under that candidate. The candidate remains isolated from the default prompt and main agent. |
| [Judge calibration](evaluations/README.md) | The raw judge agreed with all five human-labelled policy cases in the recorded invocation. | Five policy cases do not establish calibration for naturalness, consent, or general conversational quality. |

**The committed evidence does not establish a complete seventeen-scenario pass under the latest isolated candidate prompt.**
Different experiments must not be combined into that claim. Scripted orchestration tests also do not establish live model debugging ability.
Exact conversations, scores, and iteration counts can differ between provider runs.

Each new `artifacts/<run-id>/run.json` contains prompts, scenarios, tool evidence, booking state, scores, and failure diagnoses.
It also contains repair reasons, diffs, source hashes, activation results, and initial-to-final score changes.
Passing, exhausted, failed, and interrupted iterations retain their actual state. Missing scores and deltas remain null.
`monitor.json` supplies the redacted observation stream. Full local artifacts remain ignored.

Export a completed fictional run for review:

```sh
uv run --all-packages python scripts/export_refinement_run.py artifacts/RUN_ID \
  --output examples/my-refinement-run
```

Use a new output directory to preserve earlier evidence.
Exporting an error run requires `--include-incomplete`; its errors and incomplete flags remain visible.
The exporter excludes provider headers, URLs, debug events, and environment configuration. It redacts known credential values.
Examine exported content before sharing it. Only fictional customer data belongs in repository examples.

## Production work still required

- Isolate generated code in disposable environments. Host permissions, function limits, and tests do not provide execution isolation.
- Authenticate customers and authorize every booking operation. An integration key, caller ID, or booking reference does not establish ownership.
- Add expiring cost previews for baggage and reschedules. Bind consent to the exact action, booking version, and full settlement.
- Implement real payment processing and settlement. Pending special items and review-required refunds are not completed financial operations.
- Add aggregate provider-spend limits and crash recovery. Current timeouts, checkout locking, and in-process rollback do not provide durable deployment transactions.
- Add dashboard viewer authentication, artifact access controls, retention, deletion, and production personal-data handling across local and provider storage.
- Expand independently labelled evaluation cases and difficult interactions. Include multiple passengers, identity conflicts, longer recovery, and real audio behavior.
- Rerun the complete suite before promoting an experimental prompt. Keep test databases, agents, and credentials separate from production.

See [assessment boundaries and production work](docs/refinement.md#assessment-boundaries-and-production-work) for details.

## Repository map and maintenance

| Path | Responsibility |
| --- | --- |
| `apps/api/` | FastAPI routes, booking service, JSON policy calculations, PostgreSQL models, and Alembic migrations. |
| `apps/refiner/` | Host CLI, simulation/evaluation/repair stages, provider adapters, verification, reload, and artifact output. |
| `apps/dashboard/` | Three observation views, shared UI components, and server-side monitoring proxy. |
| `packages/contracts/` | Shared Python contracts, including concrete monitoring payloads and reserved event interfaces. |
| `config/` | Portable webhook schemas and worker configuration. |
| `data/flights/` | Trusted fictional seed dataset and database instructions. |
| `knowledge/` | Six policy JSON files and an ignored source-staging directory. |
| `prompts/` and `scenarios/` | Default assistant prompt and executable customer expectations. |
| `examples/` and `evaluations/` | Sanitized provider-run evidence and human-labelled judge cases. |
| `tests/` and `.github/workflows/` | Local verification and CI. |
| `artifacts/` and `.local/` | Ignored runtime output and account-specific configuration. |

Python monitoring contracts and their TypeScript equivalents are maintained separately. Update both when payloads change.
Retain documented extension interfaces, historical migrations, compatibility redirects, and shared shadcn theme variables.
The local design skill is ignored and untracked. That change did not remove its earlier Git history.

Install new shadcn components from `apps/dashboard` with the CLI:

```sh
npx shadcn@latest add COMPONENT
```

Compose installed components with Tailwind utilities and SVG icons. See [development guidance](docs/development.md) for dependency and feature workflows.
For new database models, generate a migration, examine it, and apply it explicitly:

```sh
uv run --package airline-api alembic -c apps/api/alembic.ini revision --autogenerate -m "describe schema"
make migrate
```

Keep this README current when a design decision changes.
State the decision, reason, cost, implementation status, and supporting evidence. Separate proposed work from completed behavior.
Preserve failed experiments and historical scores. Do not silently replace them with later results.

Use [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/STE_faq.html) for documentation.
Use short sentences, active voice, and one consistent name for each technical concept.
Give one instruction per step. Define necessary technical terms. Keep command names, paths, and API identifiers exact.

Further detail: [architecture](docs/architecture.md), [API](docs/api.md), [ElevenLabs](docs/elevenlabs.md), [refinement](docs/refinement.md), and [monitoring](docs/monitoring.md).
