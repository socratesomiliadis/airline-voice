# Fictional flight database

`week_2026_11_09.json` is the reproducible seed dataset for the PostgreSQL flight
database. The mutable database tables are the booking APIs' source of
flight schedules, cabin availability, and fares. The JSON is seed input, not a
second live inventory store.

All services, seat counts, and prices are fictional. Airport codes and time zones
describe the locations used by the sample routes.

## Dataset

- Week: November 9–15, 2026, inclusive, by each departure airport's local date.
- 112 flights, with 16 departures on each of the seven days.
- San Francisco (SFO) to/from Los Angeles (LAX), Seattle (SEA), New York (JFK),
  Chicago (ORD), Toronto (YYZ), and London (LHR).
- Los Angeles and Seattle have two departures per direction daily; the other
  destinations have one per direction daily.
- Three cabins per flight: economy, premium economy, and business.
- Six fare offers per flight: economy basic/standard/flexible, premium economy
  standard/flexible, and business business.
- 336 cabin inventory rows and 672 fare offers, with varying prices and availability.
- Low-availability economy examples and some sold-out business cabins.

Departure and arrival timestamps include UTC offsets. PostgreSQL stores them as
`timestamptz`; each airport's IANA time zone supports local-time display and date
searches. Overnight arrivals can fall after the final departure date of the week.

Prices are integer USD cents per adult passenger for one flight segment, including
fictional taxes and excluding optional services. Fare tiers correspond to the
policy JSON files under `knowledge/`. A seat class and a fare tier are separate:
for example, economy flexible is still an economy seat.

Each policy JSON declares these same seat classes, fare tiers, offered combinations,
route examples, currency units, and inventory field references. Baggage and refund
rules use the purchased fare tier, including standard/flexible in premium economy.
Tests in `tests/test_knowledge_alignment.py` detect drift between these sources.

Initial unavailable seats are fictional starting occupancy. They do not represent
generated passenger or booking records. No customer records are seeded.

## Tables

| Table | Contents | Identity |
| --- | --- | --- |
| `airports` | Code, name, city, country, IANA time zone | Airport code |
| `flights` | Number, route, airline, timestamps, route type, status | Stable UUID |
| `flight_cabins` | Capacity and mutable available seats per cabin | Flight ID + seat class |
| `flight_fares` | Price and currency per cabin/fare tier | Flight ID + seat class + fare tier |

All fare tiers within a cabin share its one `available_seats` value. They do not
have independent inventories. Database constraints reject negative availability,
availability above capacity, invalid cabin/fare combinations, nonpositive prices,
unknown parent records, and arrival times before departure.

## Create and populate locally

From the repository root, with dependencies installed and Docker running:

```sh
docker compose up -d --wait database
make migrate
make seed-flights
```

The migration creates the tables. The seed command validates the complete dataset,
then imports missing rows in a single transaction. Repeating it preserves existing
rows, including seat counts, flight status, and prices changed by API operations.
It does not reset inventory, update existing prices, or delete records.

To validate the JSON without connecting to PostgreSQL:

```sh
uv run --package airline-api airline-seed-flights --validate-only
```

An alternative seed file can be selected with `--file path/to/file.json`. The
command reads the database address from the existing `DATABASE_URL` setting.
Editing a seed file and rerunning the command does not overwrite existing records.

## Populate through the API container

The API image includes the dataset and the seed command. With the database running:

```sh
docker compose build api
docker compose run --rm --no-deps api alembic -c apps/api/alembic.ini upgrade head
docker compose run --rm --no-deps api airline-seed-flights
```

API startup does not run migrations or seed the database automatically.

## Inspect available flights

Open a SQL prompt using the database container's configured credentials:

```sh
docker compose exec database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Example search for available SFO–JFK fares:

```sql
SELECT f.id, f.flight_number,
       f.departure_at AT TIME ZONE a.timezone AS local_departure,
       c.seat_class, c.available_seats,
       p.fare_tier, p.price_cents, p.currency
FROM flights AS f
JOIN airports AS a ON a.code = f.origin_code
JOIN flight_cabins AS c ON c.flight_id = f.id
JOIN flight_fares AS p ON p.flight_id = c.flight_id AND p.seat_class = c.seat_class
WHERE f.origin_code = 'SFO'
  AND f.destination_code = 'JFK'
  AND f.status = 'scheduled'
  AND c.available_seats > 0
ORDER BY f.departure_at, c.seat_class, p.price_cents;
```

Booking, cancellation, rescheduling, and booking-item operations are implemented
and update these tables transactionally. Active passenger/flight allocations are
unique, cabin rows are locked during seat changes, and successful retry receipts
are persisted. Booking and passenger records survive application restarts. See
the [API reference](../../docs/api.md) and [webhook setup](../../docs/elevenlabs.md).

To use the fixed sample week after its real departure dates, set `SIMULATION_NOW`
to a timezone-aware pre-departure timestamp such as `2026-11-05T12:00:00Z`. The
default business clock is real UTC time; past departures are unavailable.

## Verification

Dataset validation tests run without PostgreSQL. To run the database integration
test, set `TEST_DATABASE_URL` to an accessible PostgreSQL database whose role may
create databases, then run:

```sh
uv run --all-packages pytest tests/test_flight_database.py
```

The test creates and removes its own uniquely named database. It checks migrations,
seed repeatability, preservation of writes, inventory/price constraints, and schema
agreement with the ORM models. CI supplies its own PostgreSQL service for this test.
