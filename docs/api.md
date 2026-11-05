# Booking API

All application paths below start with `/api/v1`. Interactive schemas and request
examples are available at `/docs`; the machine-readable contract is `/openapi.json`.

`GET /health` reports process liveness as `{"status":"ok","mode":"simulation"}`.
It does not assert database readiness.

## Setup and authentication

Start PostgreSQL, run `make migrate`, and run `make seed-flights`. Start the API
with `make dev-api`, which checks for an existing server on port 8000 first.
Commands run from the repository root. For the fixed November flight fixtures,
the optional `SIMULATION_NOW=2026-11-05T12:00:00Z` business clock keeps departures
available after their real dates have passed.

Flight and booking endpoints accept `X-Agent-Api-Key`, matched against
`AGENT_API_KEY`. Configure the same secret for trusted simulation clients and
ElevenLabs tools. When a key is configured, missing or incorrect keys return `401`.
An unset key permits local development/test calls; production returns `503` until
authentication is configured. This is trusted service authentication, not a
consumer login or identity-verification flow.

## Endpoints

| Method | Path | Result |
| --- | --- | --- |
| GET | `/flights` | Search current available cabin/fare offers |
| POST | `/bookings` | Create a booking and reserve seats; returns `201` |
| GET | `/bookings` | List committed bookings; supports `caller_id`, `limit`, `offset` |
| GET | `/bookings/{reference}` | Retrieve the current booking and its saved history |
| POST | `/bookings/{reference}/cancel` | Cancel and release seats once |
| POST | `/bookings/{reference}/reschedule` | Move a booking to a flight on the same route |
| POST | `/bookings/{reference}/items` | Add checked bags or pending special-item requests |

Booking paths accept the generated ten-character reference, case-insensitively,
or the booking UUID. All data is shared in PostgreSQL: a new caller or application
instance can retrieve and update bookings created by an earlier caller.

## Search

Supported filters:

- `destination`, `origin`: IATA code or exact city name, case-insensitively.
- `departure_date`: `YYYY-MM-DD` in the origin airport's local time.
- `min_price_cents`, `max_price_cents`: bounds on the per-passenger fare in USD cents.
- `seat_class`: `economy`, `premium_economy`, or `business`.
- `fare_tier`: `basic`, `standard`, `flexible`, or `business`.
- `passengers`: required seat count, from 1 to 9; defaults to 1.
- `sort_by`: `departure` or `price`; defaults to `departure`.
- `limit`, `offset`: pagination, with a maximum of 200 offers per page.

Filters can be used individually or together. Only scheduled, future departures
with enough available cabin seats are returned. Multiple fare tiers share that
cabin's seat count. Sold-out cabins are excluded. `has_more` indicates another
page is available. Empty searches return an empty `offers` array.

```sh
curl 'http://localhost:8000/api/v1/flights?origin=SFO&destination=JFK&departure_date=2026-11-09&max_price_cents=40000&sort_by=price'
```

Each offer contains the flight UUID/number, airport codes/cities, UTC and local
timestamps, route type, cabin, tier, available seats, per-passenger price, group
total, currency, and the corresponding checked-bag allowance. Prices include
fictional taxes and exclude optional services.

## Book

Use the exact `flight_id`, cabin, tier, and per-passenger price from search:

```json
{
  "idempotency_key": "scenario-001-book-001",
  "caller_id": "simulated-call-001",
  "flight_id": "<flight UUID from search>",
  "seat_class": "economy",
  "fare_tier": "standard",
  "expected_unit_price_cents": 29400,
  "passengers": [
    {"passenger_id": "customer-001", "full_name": "Alex Example"}
  ]
}
```

`passenger_id` is a stable customer identifier supplied by the application or
simulation. It is normalized case-insensitively and must be reused across calls.
The database prevents that passenger from holding two active bookings on the same
flight, including across different cabins or fare tiers. A group has up to nine
distinct passengers; seats and prices apply to the entire group atomically.

The response contains `reference`, booking status, fare and original paid-price
snapshots, passengers, current flight details, extras, and audit/financial events.
The fare is rechecked against `expected_unit_price_cents` before seats are taken.
A price change returns `409 fare_price_changed`; search and confirm again.

## Idempotency and concurrency

Every mutation requires an `idempotency_key` of 8–128 characters and `caller_id`.
Use a globally unique action key and preserve it and the payload on retries.
Use a new key for a new customer action. A conversation ID alone is insufficient
because one conversation can perform several actions.

Successful response snapshots are stored transactionally in `api_operations`.
Concurrent repeats of an identical request return that original result without
allocating seats, adding items, or recording charges twice. Reusing a key for a
different payload or operation returns `409 idempotency_conflict`. REST and
webhook tools use the same receipts. To see changes made after the original
response, retrieve the booking by reference.

Booking and cabin row locks, active passenger/flight uniqueness, and database
capacity constraints protect concurrent writes. Reschedules lock both flight
inventories in a consistent order. Any error rolls back the complete operation;
failed requests do not leave a successful retry receipt behind.

## Cancel

`POST /bookings/{reference}/cancel`:

```json
{
  "idempotency_key": "scenario-001-cancel-001",
  "caller_id": "simulated-call-002"
}
```

Cancellation retains the booking and passenger history, changes the status to
`cancelled`, removes active passenger allocations, and releases seats exactly
once. Repeated cancellation cannot restore seats or record refunds twice.

The saved policy snapshot determines the settlement. Refundable fares, an
eligible purchase grace period, or a qualifying airline disruption can refund
the stored paid ticket value. The current selling price of that flight is never
used as the refund basis. Unused confirmed baggage fees are refunded where the
policy permits. Basic/standard settlements requiring an unavailable itemized tax
breakdown are persisted with `review_required: true`; an exact unused-tax refund
or travel-credit amount is not invented. Post-departure/no-show requests require
manual review and return a conflict without changing the booking.

## Reschedule

`POST /bookings/{reference}/reschedule` takes `idempotency_key`, `caller_id`, and
the replacement offer's `flight_id`, `seat_class`, `fare_tier`, and
`expected_unit_price_cents`. The replacement must have the same origin and
destination. Its seats are reserved and the original seats released in one
transaction; the booking keeps its reference.

The original fare tier's change rule applies. Basic does not permit voluntary
changes. Other eligible fares incur the policy change fee and applicable fare
difference. Airline disruption rebooking waives change fees and fare differences.
Checked bags are repriced against the replacement tier's allowance, with the
adjustment recorded in the same event. Special-item requests retain their pending
status. Failed changes leave the original booking and inventory intact.

## Baggage and special items

`POST /bookings/{reference}/items`:

```json
{
  "idempotency_key": "scenario-001-items-001",
  "caller_id": "simulated-call-003",
  "items": [
    {
      "passenger_id": "customer-001",
      "item_type": "checked_bag",
      "weight_kg": 20,
      "length_cm": 60,
      "width_cm": 40,
      "height_cm": 25
    },
    {
      "passenger_id": "customer-001",
      "item_type": "mobility_aid",
      "description": "Folding wheelchair; handling details to be confirmed"
    }
  ]
}
```

Each item belongs to an existing passenger on the booking. A checked bag requires
weight and all three dimensions. Included pieces, additional-piece fees,
overweight/oversized charges, and absolute acceptance limits come from the booking's
policy snapshot. Limits and fees apply per passenger. A batch succeeds or rolls
back as a whole.

Other supported types are `stroller`, `car_seat`, `medical_device`,
`sports_equipment`, `musical_instrument`, and `cabin_pet`. These are saved as
`pending_confirmation` because the current database does not establish provider
acceptance, pet capacity, or equipment compatibility. `quoted_price_cents` may be
known or null; pending items have zero charged price. A pending request is visible
to subsequent callers. Special-item approval remains a separate workflow.

## Financial simulation and policies

Responses explicitly identify `payment_mode: simulation`. Monetary events are
persisted ledger records; no card is charged, bank refund submitted, or real
airline ticket issued. `total_charged_cents`, `total_refunded_cents`, and
`total_credit_cents` describe that simulation ledger.

The API loads the six files in `KNOWLEDGE_DIR` at startup. Bookings save their
policy version and rule snapshot so later file changes do not silently alter
existing booking entitlements. Business timestamps use `SIMULATION_NOW` when
configured. Events retain real audit timestamps plus their `effective_at` business
timestamp.

## Errors and other platform routes

Business errors use:

```json
{
  "error": {
    "code": "insufficient_seats",
    "message": "Not enough seats remain in this cabin.",
    "details": {"available_seats": 0}
  }
}
```

Typical statuses are `404` for unknown bookings/flights/fares, `409` for conflicting
state or policy restrictions, and `422` for invalid measurements or input.
FastAPI validation errors use its standard `detail` array; authentication errors
also use `detail`. Unknown input fields are rejected.

Unrelated baggage inquiries, general support, conversations, knowledge ingestion,
monitoring, refinement control, and voice-session creation remain reserved `501`
routes. Agent tool webhook setup is documented in [elevenlabs.md](elevenlabs.md).
