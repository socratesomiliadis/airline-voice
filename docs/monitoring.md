# Observe the autonomous loop

The dashboard is an observation-only interface. It shows conversations as turns
arrive, tool activity, evaluation scores for each scenario and iteration, prompt
and code diffs, failure diagnoses, and the complete iteration history of a run.
The UI uses CLI-installed shadcn/ui components on Base UI (`base-nova`), including
sidebar navigation, selects, tabs, accordions, scroll areas, progress, and cards.
Feature components compose those installed primitives and a small SVG score chart.

There are no start, stop, approve, edit, retry or message-entry controls. Run,
iteration and scenario selection change only what the viewer sees.

## Local setup

Use the repository's existing API and dashboard servers. Check for listeners
before starting another server. If necessary, start them from the repository root:

```sh
make dev-api
make dev-dashboard
```

Open <http://localhost:3000>. The default view follows the latest run and the
active scenario. A selected historical iteration stays selected while the worker
continues. “Follow latest” returns to the live iteration. Chat follows new messages
until the viewer scrolls up, preserving their reading position.

The API and worker must share the same `REFINER_ARTIFACTS_DIR` (default `artifacts`
relative to the repository root). The API reads those files; it cannot control
the worker. In Compose, the API mounts the host's `./artifacts` read-only and the
dashboard connects to `http://api:8000`. For a custom artifacts location, update
the API mount as well as the worker and API settings.

`apps/dashboard/.env.local` can set the server-side `API_BASE_URL`. For local host
development, the dashboard proxy automatically reads `AGENT_API_KEY` from the
repository's root `.env`; it never includes that key in browser JavaScript.
Deployments should supply `API_BASE_URL` and `AGENT_API_KEY` directly in the
dashboard server's environment. Compose does this automatically. No `NEXT_PUBLIC`
credential is used. The two same-origin dashboard routes accept GET only:

- `/api/monitoring`: streaming observations.
- `/api/monitoring/snapshot`: the current snapshot as JSON.

Run the autonomous worker separately using the [refinement guide](refinement.md).
An empty dashboard shows that no runs are recorded; it never inserts sample
conversations or invented scores. It populates automatically once a worker starts.

## Live transport and persistence

The worker writes a redacted `monitor.json` alongside each run's existing artifacts.
It publishes on messages and corrections, tool events, evaluations, repair
proposals, validation/reload/publication stages, rollback, and completion. A
five-second worker heartbeat distinguishes an active worker from an abandoned run.
Prompt diffs are saved as `iteration-XX/prompt.patch` as well as included in the
snapshot; proposed, applied and rolled-back changes are labeled separately.

Authenticated API GET endpoints `/api/v1/monitoring/snapshot` and
`/api/v1/monitoring/events` expose only this observation data. The stream checks
artifact revisions every 500 ms and sends complete snapshots as server-sent events,
plus a transport heartbeat every ten seconds. A reconnect receives current state,
so messages are not duplicated and events missed during an API reload are recovered.
Artifacts survive API restarts; no process-local event queue is required.

The browser uses one EventSource connection across dashboard navigation. It
reconnects automatically, retains the last received view during an outage, and
shows that the connection is interrupted. A transport watchdog replaces a stream
that stops delivering heartbeats. A separate warning appears when a running
worker has not reported for thirty seconds. A stale worker is never presented
as a completed or passing run.

The store reads at most the latest 100 valid runs and ignores malformed, oversized
or symlinked observation files. Monitoring requires no database or model-provider
connection, so the UI can remain available while the booking API reloads.

## Reading scores and history

The score panel shows the four scores for the selected scenario. The trend chart
plots each criterion's **lowest score across evaluated scenarios**, with a target
line. Pending scenarios stay pending. The table exposes every individual score;
a high average cannot hide a failed criterion. Per-scenario rationale includes
failure quotes and prompt/code root causes, with exact file/function/behavior
for code failures.

Iteration history lets the viewer inspect past conversations, scores and changes.
The run summary distinguishes success, iteration-limit exhaustion and errors.
The UI presents actual recorded changes even when verification or publication
fails, with rollback/recovery status and error details.

## Verification

```sh
make check-python
make check-dashboard
```

Python tests cover publishing before conversation completion, message corrections,
tool state, redaction, prompt diffs, durable replay, authentication, empty states,
and rejection of monitoring writes. Dashboard tests cover score aggregation, diff
line numbers, streaming proxy cancellation, secret handling and error responses.
