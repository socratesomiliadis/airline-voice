# ElevenLabs booking webhook tools

## First-time setup on your own account

Install the workspace (`make setup`), start PostgreSQL, run `make migrate` and
`make seed-flights`, then start the API with `make dev-api`. Set these in `.env`:

```dotenv
ELEVENLABS_API_KEY=your-account-key
AGENT_API_KEY=your-own-shared-webhook-secret
SIMULATION_NOW=2026-11-06T12:00:00Z
PUBLIC_API_BASE_URL=https://your-public-api-origin
```

Expose the API through a public HTTPS tunnel or deployment. Check for an existing
tunnel with `pgrep -fl cloudflared` before starting one. For a local tunnel run
`cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate` and set
`PUBLIC_API_BASE_URL` to its HTTPS origin. Update the agent when that URL changes.

Create and configure a private agent in your account:

```sh
uv run --all-packages python scripts/configure_elevenlabs.py --create-agent "Airline assessment"
```

Set `ELEVENLABS_AGENT_ID` in `.env` to the printed ID. Creation uses the provider's
default voice/model; review these in your account if desired. The script attaches
six policies, seven tools, secret-header authentication and the system prompt.
Open the agent's Preview in your ElevenLabs account to speak or chat, then run
`make refine` for autonomous text simulations after setting the model credentials.

To configure an existing agent, use `--agent-id YOUR_AGENT_ID` instead. Existing
agents retain their voice/model. No account resource IDs are shipped in the repo.
Resumable manifests live under ignored `.local/elevenlabs/`. Existing agents use
their ID as the filename; a name-based creation receipt points to that same
manifest. Repeating a creation command resumes that agent. Use a different name or
`--state-file .local/another-agent.json` for an independent setup.

`AGENT_API_KEY` authenticates tools to FastAPI; `ELEVENLABS_API_KEY` authenticates
provisioning and never reaches the booking backend or model. For older checkouts,
move your own `config/elevenlabs-agent.json` to
`.local/elevenlabs/<your-agent-id>.json` before syncing that agent. Never copy
another account's resource IDs.

## Restart or update the development connection

Check existing processes before starting another backend or tunnel:

```sh
lsof -nP -iTCP:8000 -sTCP:LISTEN
pgrep -fl cloudflared
```

If needed, start Docker Desktop and the database, then run the API and tunnel in
separate terminals from the project root:

```sh
docker compose up -d database
.venv/bin/python -m uvicorn airline_api.main:app --host 127.0.0.1 --port 8000
```

```sh
cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate
```

Set `PUBLIC_API_BASE_URL` in `.env` to the HTTPS origin printed by cloudflared.
The fictional dataset uses `SIMULATION_NOW=2026-11-06T12:00:00Z` so later tests
can continue booking the November 9–15 week. Restart the backend after changing
its environment settings. Reuse the existing database; do not reset it.

Publish a changed URL, prompt, or policies using:

```sh
.venv/bin/python scripts/configure_elevenlabs.py
```

The script checks connectivity, updates the seven managed tools and shared secret,
attaches the policy documents, and publishes a private agent version. It preserves
the voice/model and records created IDs immediately for retrying an interrupted
setup. Updated policies create new document revisions; old documents are retained.
The canonical policies remain six separate JSON files in `knowledge/`. The initial
uploads are `.txt` copies because the UI file picker does not accept `.json`;
their policy content matches the JSON sources. Later script uploads use text
documents directly. The manifest below remains the backend schema contract, not
a direct provider import file; the script translates its schema dialect.

Real provider Chat Mode calls verified search, booking, retrieval from another
conversation, special items, rescheduling, and cancellation against PostgreSQL.
The cancelled synthetic booking remains as audit history. The original eight-scenario
autonomous suite passed before the suite was expanded, and synthetic spoken input was recognized and answered
with generated audio. Physical microphone and speaker quality still need a
hands-on voice check in Preview.

## Backend endpoints

The API exposes seven ordinary JSON POST endpoints for ElevenLabs webhook tools.
They call the same transactional booking service as REST, so every simulated
caller shares the same persisted bookings and seat inventory.

ElevenLabs lets a tool define its URL, method, body parameters, and secret request
headers. See the official [webhook tool configuration and authentication guide](https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools).

## Configure the tools

Start the database, apply migrations, seed flights, and run the API. For the fixed
fictional week, optionally set `SIMULATION_NOW=2026-11-06T12:00:00Z`. The API must
be reachable at your HTTPS base URL from ElevenLabs. Localhost alone is accessible
only to local simulations.

Set `AGENT_API_KEY` on the backend. For each tool, configure a secret header named
`X-Agent-Api-Key` with the same value. Keep it in ElevenLabs' secret configuration;
the model should not generate it as a body parameter.

Create these tools with method `POST` and content type `application/json`:

| Tool name | Path after your API base URL | Body model |
| --- | --- | --- |
| `get_flight_information` | `/api/v1/voice/webhooks/elevenlabs/get_flight_information` | `FlightInformationQuery` |
| `search_flights` | `/api/v1/voice/webhooks/elevenlabs/search_flights` | `FlightSearch` |
| `book_flight` | `/api/v1/voice/webhooks/elevenlabs/book_flight` | `BookFlight` |
| `get_booking` | `/api/v1/voice/webhooks/elevenlabs/get_booking` | `BookingReference` |
| `cancel_booking` | `/api/v1/voice/webhooks/elevenlabs/cancel_booking` | `CancelBookingTool` |
| `reschedule_booking` | `/api/v1/voice/webhooks/elevenlabs/reschedule_booking` | `RescheduleBookingTool` |
| `add_booking_items` | `/api/v1/voice/webhooks/elevenlabs/add_booking_items` | `AddBookingItemsTool` |

The backend contract manifest is
[`config/elevenlabs-tools.json`](../config/elevenlabs-tools.json). It lists names,
paths, methods, descriptions, the authentication header, and standard JSON Schemas
for each body. Use those contracts to configure the corresponding tool parameters.
The same schemas are available through `/openapi.json` and `/docs`.

Regenerate the manifest after changing request models:

```sh
uv run --package airline-api python -m airline_api.modules.voice.tool_contracts > config/elevenlabs-tools.json
```

Tool webhook requests contain the body described by their model directly. For
example, `get_booking` receives `{"reference":"<booking reference>"}`. The three
tools that modify an existing booking include `reference` in their body alongside
the REST mutation fields. All successful tool responses are HTTP `200` JSON.

## Agent calling behavior

1. Search for flights using airport/city, local departure date, passengers, and
   budget. Read the returned cabin, fare tier, price in cents, and shared availability.
2. Obtain customer confirmation before booking, canceling, changing, or adding
   chargeable baggage. Use a stable passenger/customer ID supplied by the application
   or simulation; reuse it on future calls.
3. Supply a unique `idempotency_key` for each customer action. HTTP retries of that
   action must preserve the key and exact body. Assign `caller_id` from the current
   conversation or simulation. A conversation can perform multiple distinct actions.
4. Book with the exact offer identifiers and `expected_unit_price_cents`. On
   `fare_price_changed` or `insufficient_seats`, search again and confirm a new choice.
5. Save the returned booking reference. A subsequent call can retrieve it even
   after the API restarts. Use `get_booking` for the latest state; retry receipts
   replay the original successful result.
6. Search replacement availability before rescheduling. Submit the reference and
   replacement offer fields. The reference remains unchanged after success.
7. Read item and settlement statuses accurately. `pending_confirmation` requests
   have been recorded but still require acceptance; `review_required` settlements
   require the missing tax/payment detail. Monetary events use a simulation ledger.

Booking responses include `flight.departure_local`, `flight.arrival_local`, and
the airport timezone names. Speak these local values; `departure_at` and
`arrival_at` can be UTC and must not be labeled local.

These routes handle agent tool invocations. Post-call transcript/audio ingestion
into the local dashboard and phone-number provisioning remain future work.
Conversation transcripts and tool results are available in ElevenLabs.

## Persistence verification

With a PostgreSQL role that may create test databases:

```sh
uv run --all-packages pytest tests/test_bookings_api.py
```

Set `TEST_DATABASE_URL` in the environment first. Tests use isolated disposable
databases and cover the tool paths, cross-caller visibility, application
restart persistence, parallel last-seat races, concurrent retries/cancellations,
reschedule rollback, duplicate passengers, policy fees, and original paid values.
