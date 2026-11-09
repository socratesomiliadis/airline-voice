# Development guidance

## Dependencies

Use `uv add --package airline-api <dependency>` or
`uv add --package airline-refiner <dependency>` for Python application dependencies.
Use `uv add --dev <dependency>` for root development tooling. Commit `uv.lock`.

Run `npm install <dependency>` in `apps/dashboard` for dashboard dependencies and
commit `package-lock.json`. The dashboard uses shadcn/ui with Base UI primitives
and the `base-nova` preset in `apps/dashboard/components.json`. Install components
with `npx shadcn@latest add <component>` from `apps/dashboard`; compose the installed
components for feature views rather than introducing replacement UI primitives.
Tailwind utilities and Lucide SVG icons provide layout, theme and icons.

Biome handles dashboard linting, formatting, and import organization. Run
`npm run format` from `apps/dashboard` to apply safe fixes and formatting.

## Adding a backend feature

1. Define domain request/result schemas in the owning module.
2. Define typed ports for implemented behavior when adapters share a boundary.
3. Add use cases that depend on ports rather than infrastructure.
4. Implement provider/repository adapters and register their dependencies.
5. Add ORM models and a reviewed Alembic revision when persistence is required.
6. Register routes only after their behavior is implemented.
7. Add behavior-focused tests for the feature.

Flight and booking routes have implemented schemas, agent-key authentication,
durable idempotency, explicit transactions, and database integration tests. See
`docs/api.md`. The API exposes only implemented routes.

## Refinement development

The host CLI runs the concrete pipeline under `apps/refiner`. Keep external LLM,
HTTP, WebSocket, filesystem and subprocess operations in adapters, and extend
validated contracts in `models.py` when adding evidence or repair behavior.
Regression tests in `tests/test_refinement.py` exercise mixed repairs, termination,
provider contracts, evidence checks and rollback without external credentials.
See [the refinement guide](refinement.md) before changing runtime policies.

## Dashboard monitoring

Observation schemas live in `packages/contracts/monitoring.py`, mirrored by the
dashboard's typed contracts. The worker publishes snapshots; the API only reads
and streams them. Keep credentials in the server-side proxy, and keep view state
separate from autonomous execution. Add no mutation routes or controls to the
observation UI. See [streaming, configuration and tests](monitoring.md).

## Local servers

Check for an existing server before starting one. `make dev-api` and
`make dev-dashboard` provide listener checks. They use ports 8000 and 3000;
Compose uses those same defaults. Stop the specific existing service or choose
another port if needed. Avoid running duplicate servers against the same port.
