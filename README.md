# Airline Voice

Scaffold for an autonomous airline customer service agent powered by ElevenLabs,
with a FastAPI backend, PostgreSQL persistence, a Python refinement worker, and
a Next.js monitoring dashboard.

**This repository intentionally contains no business logic.** Feature routes return
`501 Not Implemented`; the worker cannot execute a run; dashboard views show empty
states. Only application startup, configuration, database session plumbing, route
registration, navigation, and development infrastructure are implemented.

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
    migrations/            Alembic environment; no domain revisions
  refiner/
    src/airline_refiner/
      pipeline/            Context, runner, and stage protocols
      adapters/            Reserved API, model, and workspace adapters
  dashboard/
    src/
      app/                 Next.js App Router pages
      components/          Shared layout and UI components
      features/monitoring/ Monitoring view shells
      lib/api/             Future API and event-stream contracts
packages/contracts/        Shared Python payload and event contracts
config/                    Refinement configuration placeholders
prompts/                   Future versioned prompt assets
scenarios/                 Future simulated customer scenarios
knowledge/                 Knowledge source staging location
artifacts/                 Ignored local refinement output
tests/                     Infrastructure and scaffold boundary checks
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

The refinement container is optional and only displays CLI help:

```sh
docker compose --profile refinement run --rm refiner --help
```

Passing `run` deliberately exits with status 2 and performs no work. The worker
has no source-code mount, Docker socket mount, or active patching capability.

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

These targets check whether their port already has a listener before starting a
development server. Do not start a local app on a port occupied by Compose.
The dashboard makes no API requests yet. Both application shells can start without
PostgreSQL or ElevenLabs credentials; liveness does not imply dependency readiness.

Inspect the worker CLI:

```sh
uv run --package airline-refiner airline-refiner --help
```

## Configuration

The API reads `.env` relative to its working directory. Run local Python commands
from the repository root. Compose injects container-specific addresses, including
the `database` hostname instead of `localhost`. The dashboard has a separate
`.env.local`; its reserved `API_BASE_URL` is server-side and currently unused.

ElevenLabs credentials are reserved for the backend. There are no provider calls,
webhook verification, authentication, or customer-data handling in this scaffold.
The defaults are for local development; deployment configuration is deferred.

`config/refinement.example.toml` contains empty sections, with no active thresholds,
retry limits, model selection, or mutation policy. The worker does not load it yet.

## Database migrations

The async SQLAlchemy base and session factory are ready for future models. No
domain tables, schema migrations, seed data, or auto-create behavior are supplied.
Alembic reads `DATABASE_URL` through the API settings.

After adding and registering models in `infrastructure/database/models/`:

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
build. Tests require no external services and verify that feature routes and worker
execution stay inactive.
CI also builds all three application images.

## Architecture and next implementation steps

See [architecture](docs/architecture.md), [development guidance](docs/development.md),
and the [reserved API surface](docs/api.md). Domain schemas, persistence models,
provider integration, real-time transport, evaluation criteria, and the refinement
loop are intentionally left for subsequent implementation.
