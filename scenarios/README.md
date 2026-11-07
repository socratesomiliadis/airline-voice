# Simulation scenarios

`airline.json` is the executable fictional customer suite for the autonomous
refiner. Each scenario supplies a unique ID, goal, customer facts, expected
outcome, required tool names, and optional fresh prerequisite booking.

Run from the repository root:

```sh
uv run --package airline-refiner airline-refiner run
```

See [the refinement guide](../docs/refinement.md) for configuration, fixtures,
scoring, repairs and saved run evidence. Do not add real customer data.

## Assessment coverage

| Requested call type | Executable scenario |
| --- | --- |
| Next available flight | `next-available-flight` |
| Cheapest in the following week | `cheapest-following-week` |
| Pet policy | `cabin-pet` |
| Reschedule | `reschedule-booking` |
| Cabin/hold baggage allowance, weight and fees | `baggage-policy` |
| Refund/cancellation | `cancel-booking` |
| Seat preference | `seat-preference` (window); API regressions cover aisle and extra legroom too |
| Extra bag/special item | `checked-baggage`, `cabin-pet` |
| Check-in, gate, status | `check-in-policy`, `flight-information` |
| Mobility/special needs | `special-assistance` |

`book-flight` and `basic-change-restriction` add regressions. The business clock
is November 6, 2026; the following calendar week is November 9–15. Each iteration
creates fresh fixtures and releases their seats afterward. Gate/status inquiries
need no reference. Seat preferences remain unassigned requests.

Each scenario's `assertions` object is an executable acceptance contract. It can
specify saved status/route/date/fare, seat request, item counts/status/charges,
read-only behavior, unchanged bookings, tool ordering and exact parameters.
Next/cheapest selection also checks a REST reference offer captured before the
conversation. These checks are enforced independently of the LLM's scores.
Policy wording and conversational confirmation remain the LLM judge's job.
