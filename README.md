# Airline Voice

An autonomous airline customer service agent powered by ElevenLabs,
with a FastAPI backend, PostgreSQL persistence, a Python refinement worker, and
a Next.js monitoring dashboard.

**Persistent booking APIs and ElevenLabs webhook tools are implemented.** The API
searches flights, books travel, retrieves bookings, cancels or reschedules, and
adds baggage or special-item requests, records seat preferences, and provides
fictional flight gates/status. Operations use PostgreSQL transactions,
shared cabin inventory, versioned JSON policies, and durable retry receipts.
Payments are simulated ledger entries. The autonomous refinement worker simulates
text conversations, scores them, repairs prompts and backend code, reloads the
service and repeats. The read-only dashboard streams live conversations, evaluation
scores, prompt/code diffs and iteration history. Other reserved platform features
remain unimplemented.

## Repository layout

```text
apps/
  api/
    src/airline_api/
      api/                 HTTP composition, dependencies, and liveness
      core/                Settings, logging, and placeholder responses
      modules/             Feature routers and application ports
        bookings/          Booking, cancellation, rescheduling
        baggage/           Baggage inquiries
        support/           General requests and escalation
        conversations/     Conversation records and transcripts
        knowledge/         Document ingestion and retrieval
        voice/             ElevenLabs sessions, webhooks, and tools
        monitoring/        Monitoring events
        refinement/        Run control and result persistence
      infrastructure/      Database and reserved provider adapters
    migrations/            Flight inventory and booking schema migrations
  refiner/
    src/airline_refiner/
      pipeline/            Autonomous runner, simulation, evaluation, repair
      adapters/            REST, Chat Mode, model, patch and artifact adapters
  dashboard/
    src/
      app/                 Next.js App Router pages
      components/          Shared layout and UI components
      features/monitoring/ Live conversations, scores, diffs, and history
      lib/api/             Read-only API proxy and observation contracts
packages/contracts/        Shared Python payload and event contracts
config/                    Webhook contracts and runtime refinement configuration
data/flights/              Fictional flight week and database setup instructions
prompts/                   Agent system prompt
scenarios/                 Executable fictional customer suite
knowledge/                 One JSON file per fictional policy and source staging
artifacts/                 Ignored local refinement output
tests/                     Policy, API, concurrency, persistence, and infrastructure checks
docs/                      Architecture and extension guidance
```

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Node.js 22+ and npm.
- Docker with Compose for the containerized stack.
- `lsof` for the local development server port guards in the Makefile.

Python packages share `uv.lock`; the dashboard uses `package-lock.json`.

## Run with Docker Compose

```sh
cp .env.example .env
docker compose up --build
```

- Dashboard: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>
- API liveness: <http://localhost:8000/health>
- PostgreSQL: `localhost:5432` (local development credentials in `.env.example`).

The default stack starts PostgreSQL, the API, and the dashboard. Named volumes
preserve database data and future refinement artifacts. `docker compose down`
stops the stack without deleting these volumes. Published ports bind to localhost.

Initialize a new database before using booking operations:

```sh
docker compose run --rm --no-deps api alembic -c apps/api/alembic.ini upgrade head
docker compose run --rm --no-deps api airline-seed-flights
```

The refinement container is optional and only displays CLI help:

```sh
docker compose --profile refinement run --rm refiner --help
```

Run autonomous refinement on the host so the worker can edit source, execute
regression tests and reload the existing API. The container is for CLI inspection
and has read-only source asset mounts. See [the refinement guide](docs/refinement.md).

## Run locally

From the repository root:

```sh
cp .env.example .env
cp apps/dashboard/.env.example apps/dashboard/.env.local
make setup
docker compose up -d database
```

Start each app in a separate terminal:

```sh
make dev-api
```

```sh
make dev-dashboard
```

`make dev-api` runs without auto-reload so repairs are verified before activation.
Use `make dev-api-watch` only for interactive editing; refinement refuses an API
started with `--reload`.

These targets check whether their port already has a listener before starting a
development server. Do not start a local app on a port occupied by Compose.
The dashboard connects through a server-side, read-only observation proxy. It
updates automatically when the worker starts; an empty workspace contains no
sample data. See [dashboard setup and streaming](docs/monitoring.md). API liveness
does not imply booking database or model-provider readiness.

Provision your own agent using the [first-time ElevenLabs setup](docs/elevenlabs.md).
Run the autonomous refinement worker after configuring its model credentials:

```sh
make refine
```

It stops when every scenario criterion scores at least 8/10, or after 5 iterations.
Override these defaults with `--pass-score` and `--max-iterations`, or edit
`config/refinement.example.toml`. Transcripts, evaluations, patches and logs are
saved under `artifacts/<run-id>/`. See [setup and recovery](docs/refinement.md).

## Configuration

The API reads `.env` relative to its working directory. Run local Python commands
from the repository root. Compose injects container-specific addresses, including
the `database` hostname instead of `localhost`. The dashboard has a separate
`.env.local`; `API_BASE_URL` is server-side. Locally, the observation proxy reads
`AGENT_API_KEY` from the repository root `.env`.

Set `AGENT_API_KEY` and configure the matching `X-Agent-Api-Key` secret header for
ElevenLabs webhook tools and trusted simulation clients. Development/test mode
allows local requests when no key is configured; production fails closed with
`503` until a key is set. Receiving tool calls does not require an ElevenLabs API
key. These endpoints do not make outbound provider calls or process real payments.

`KNOWLEDGE_DIR` locates the policy JSON files. The optional timezone-aware
`SIMULATION_NOW` fixes the business clock for the sample week, for example
`2026-11-05T12:00:00Z`. Without it, flight eligibility uses the current UTC time.
Audit events keep real timestamps and include the effective business time.

`config/refinement.example.toml` defines quality thresholds, iteration and timeout
limits, separate customer/evaluator/repair models, editable source roots, and
verification/reload commands. Set `ANTHROPIC_API_KEY` (or `REFINER_MODEL_API_KEY`)
for structured Anthropic model calls. The worker uses the existing `ELEVENLABS_API_KEY`,
`ELEVENLABS_AGENT_ID`, and `AGENT_API_KEY`.

## Database migrations

The database contains airports, flights, cabin inventory, fare offers, bookings,
passengers, active passenger allocations, extras, audit events, and idempotency
receipts. Alembic reads `DATABASE_URL` through API settings. Create the schema and
populate the fictional November 9–15, 2026 flight week:

```sh
make migrate
make seed-flights
```

The seed contains 112 flights across seven airports, three seat classes, and six
fare offers per flight. Repeated imports preserve existing inventory and prices.
See [flight database setup](data/flights/README.md) for the schema, container
commands, and example queries. Migrations and seeds never run during API startup.

After adding further models in `infrastructure/database/models/`:

```sh
uv run --package airline-api alembic -c apps/api/alembic.ini revision --autogenerate -m "describe schema"
make migrate
```

Review generated migrations before applying them. Migrations are an explicit
operation and are not run during API startup.

## Verification

```sh
make check
docker compose config --quiet
```

Checks cover Python linting, formatting, strict typing, infrastructure smoke tests,
dashboard linting and formatting with Biome, TypeScript, and the Next.js production
build. Dataset and scaffold tests require no external services. The PostgreSQL
integration test runs when `TEST_DATABASE_URL` is set and uses its own disposable
database. Backend repair verification always requires PostgreSQL and rejects
skipped required regressions; run `make verify-backend` to execute that gate using
`.env`. CI uses the strict gate and also builds all three application images.

## Architecture and next implementation steps

See [architecture](docs/architecture.md), [development guidance](docs/development.md),
the [booking API reference](docs/api.md), [ElevenLabs setup](docs/elevenlabs.md),
and the [fictional JSON knowledge base](knowledge/README.md).
The [refinement worker](docs/refinement.md) implements outbound text conversations,
evaluation, diagnosis, prompt/code repair and deployment. The [observation UI](docs/monitoring.md)
streams its progress without exposing run controls. Other reserved API features
remain for subsequent implementation.

## Assessment scenarios and recorded evidence

Thirteen scenarios cover all ten requested call types, including next departure,
cheapest across a week, seat preferences, baggage policy and gate/status lookup.
Seat preferences are saved requests, not guaranteed assignments. Flight status
and gates are fictional database records. See [coverage](scenarios/README.md).

The [recorded example](examples/recorded-run/README.md) includes a real provider
run, starting/final prompts, scores, diagnoses, changes and an improvement summary.
Raw local artifacts stay ignored; export completed runs with:

```sh
uv run --all-packages python scripts/export_refinement_run.py artifacts/RUN_ID --output examples/recorded-run
```

The exporter includes conversation/tool evidence and saved booking state, excludes
provider headers, URLs, debug events and environment configuration, and redacts
known credentials. Only fictional customer data belongs in examples.

Each new run's `run.json` is self-contained: prompts, scenario assertions, tool and
booking evidence, scores, root causes, repair proposals/reasons, diffs, deployment
outcomes and first-to-final score changes are included. Terminal and interrupted
iterations are finalized. See [report and verification semantics](docs/refinement.md).
