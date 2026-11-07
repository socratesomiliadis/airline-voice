# Development guidance

## Dependencies

Use `uv add --package airline-api <dependency>` or
`uv add --package airline-refiner <dependency>` for Python application dependencies.
Use `uv add --dev <dependency>` for root development tooling. Commit `uv.lock`.

Run `npm install <dependency>` in `apps/dashboard` for dashboard dependencies and
commit `package-lock.json`. Use the shadcn `add` command if shadcn components are
introduced. The scaffold currently uses small composable React components,
Tailwind utility classes, and Lucide SVG icons without shadcn.

Biome handles dashboard linting, formatting, and import organization. Run
`npm run format` from `apps/dashboard` to apply safe fixes and formatting.

## Adding a backend feature

1. Define domain request/result schemas in the owning module.
2. Replace generic payloads in the relevant ports with those types.
3. Add use cases that depend on ports rather than infrastructure.
4. Implement provider/repository adapters and register their dependencies.
5. Add ORM models and a reviewed Alembic revision when persistence is required.
6. Replace the corresponding `501` route only when its behavior is implemented.
7. Replace the scaffold boundary test for that route with behavior-focused tests.

Flight and booking routes have implemented schemas, agent-key authentication,
durable idempotency, explicit transactions, and database integration tests. See
`docs/api.md`. Other route names still reserve an unimplemented API surface.

## Refinement development

The host CLI runs the concrete pipeline under `apps/refiner`. Keep external LLM,
HTTP, WebSocket, filesystem and subprocess operations in adapters, and extend
validated contracts in `models.py` when adding evidence or repair behavior.
Regression tests in `tests/test_refinement.py` exercise mixed repairs, termination,
provider contracts, evidence checks and rollback without external credentials.
See [the refinement guide](refinement.md) before changing runtime policies.

## Connecting dashboard data

Implement the API boundary in `src/lib/api/`, then use it through feature-owned
data access. Keep provider secrets server-side. Implement live transport through
the event-stream boundary, including connection status and cleanup, before changing
the shell's static connection indicator. Replace empty states with actual records
only after the corresponding API endpoints are available.

## Local servers

Check for an existing server before starting one. `make dev-api` and
`make dev-dashboard` provide listener checks. They use ports 8000 and 3000;
Compose uses those same defaults. Stop the specific existing service or choose
another port if needed. Avoid running duplicate servers against the same port.
