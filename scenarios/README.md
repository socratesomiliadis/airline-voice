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
Next/cheapest selection uses an independent calculation over trusted fixture data,
with a captured business clock and dataset hash; it never uses the search service
as its reference. Use a dedicated seeded database with no external inventory writers. These checks are enforced independently of the LLM's scores.
Policy wording and conversational confirmation remain the LLM judge's job.


Four additional interaction regressions expand the suite to seventeen scenarios:

- `ambiguous-date-correction`: an ambiguous city/date, then a changed travel date;
  the final search must use the corrected date and no purchase is authorized.
- `unavailable-inventory`: a sold-out business cabin, a question about fare tiers,
  and refusal to buy any offered alternatives.
- `withdrawn-consent`: initial purchase intent followed by an interruption before
  consent; no mutation, including a rejected mutation attempt, is allowed.
- `policy-reasoning-challenge`: a challenge to elapsed-time reasoning; the booking
  must remain unchanged, and policy reasoning remains subject to factual/judge checks.

The customer model reveals details progressively and follows scenario-specific
refusals and interruptions. These are stochastic interaction tests, not an assurance
that all difficult conversations are covered. Multi-passenger interactions,
contradictory identity claims and longer recovery sequences still need dedicated
scenarios and human review. Policy assertions and no-mutation checks alone do not
prove that each desired conversational behavior occurred.
