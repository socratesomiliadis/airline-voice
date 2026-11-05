# ElevenLabs booking webhook tools

The API exposes six ordinary JSON POST endpoints for ElevenLabs webhook tools.
They call the same transactional booking service as REST, so every simulated
caller shares the same persisted bookings and seat inventory.

ElevenLabs lets a tool define its URL, method, body parameters, and secret request
headers. See the official [webhook tool configuration and authentication guide](https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools).

## Configure the tools

Start the database, apply migrations, seed flights, and run the API. For the fixed
fictional week, optionally set `SIMULATION_NOW=2026-11-05T12:00:00Z`. The API must
be reachable at your HTTPS base URL from ElevenLabs. Localhost alone is accessible
only to local simulations.

Set `AGENT_API_KEY` on the backend. For each tool, configure a secret header named
`X-Agent-Api-Key` with the same value. Keep it in ElevenLabs' secret configuration;
the model should not generate it as a body parameter.

Create these tools with method `POST` and content type `application/json`:

| Tool name | Path after your API base URL | Body model |
| --- | --- | --- |
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

These routes handle agent tool invocations. Post-call transcript/audio ingestion
and outbound ElevenLabs agent/session provisioning remain future work. No tool
configuration or agent has been uploaded to an ElevenLabs account by this change.

## Persistence verification

With a PostgreSQL role that may create test databases:

```sh
uv run --all-packages pytest tests/test_bookings_api.py
```

Set `TEST_DATABASE_URL` in the environment first. Tests use isolated disposable
databases and cover all six tool paths, cross-caller visibility, application
restart persistence, parallel last-seat races, concurrent retries/cancellations,
reschedule rollback, duplicate passengers, policy fees, and original paid values.
