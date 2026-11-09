# Knowledge assets

Each policy has its own JSON file for **Airline Voice Demo**, a fictional airline.
Its rules, fees, limits, and deadlines are editable development data, not approved
policies for a real airline.

Policy files:

- [pet_policy.json](pet_policy.json): pet eligibility, carriers, reservations,
  fees, and service-dog exceptions.
- [baggage.json](baggage.json): cabin and checked allowances, additional-piece,
  weight and size fees, infant equipment, and unused-fee refunds.
- [special_assistance.json](special_assistance.json): accessibility assistance,
  mobility aids, service dogs, and medical devices.
- [check_in.json](check_in.json): online and airport check-in, bag drop, boarding,
  and gate deadlines.
- [cancellation_and_refunds.json](cancellation_and_refunds.json): cancellation
  benefits, fare-specific refunds, credits, disruptions, optional services,
  no-shows, and refund processing.
- [booking_changes.json](booking_changes.json): rescheduling fees and fare differences.

Each file includes its own metadata describing the fictional status, version,
language, currency, units, and scope. Its `policy` object contains a summary,
retrieval keywords, clarification questions, and rules with stable IDs. Each rule
contains a customer-facing `answer` and structured `details`. Related rules
reference those IDs, including references across policy files.

## Alignment with flight inventory

Every policy file includes an `inventory_reference` for the November 9–15, 2026
flight dataset and the database fields used for current schedules, seats, and
prices. The sample dates describe the flight fixtures, not an expiry date for the
policies. Flight prices and seat counts remain in PostgreSQL and are not copied
into policy answers.

The shared scope distinguishes `seat_classes` from `fare_tiers` and lists the
offered combinations in `fare_tiers_by_seat_class`. Economy has basic, standard,
and flexible tiers; premium economy has standard and flexible; business has the
business tier. Baggage, change, and refund entitlements follow the purchased fare
tier. Premium economy does not automatically receive business entitlements.

Policy fees are in USD dollars; `flight_fares.price_cents` is in USD cents. Flight
quotes include sample taxes and exclude optional services. Check-in deadlines use
the relevant departure timestamp and origin airport's IANA time zone. US-to-US
sample flights use domestic rules; Toronto and London flights use international
rules in either direction.

Passenger seat inventory does not confirm pet space, assistance arrangements,
device acceptance, or original payment amounts needed for refunds. The policy
answers identify where separate confirmation is still required.

Alignment checks compare all six policy files with every seeded cabin/fare/route
combination and validate shared metadata and cross-references:

```sh
uv run --all-packages pytest tests/test_knowledge_alignment.py
```

Keep an answer and its structured details consistent when editing. Fees state
their charging unit; domestic and international amounts are separate where they
differ. Additional-bag fees count from the first bag beyond the included allowance.
Increment `policy_version` when changing policy content.

Validate JSON syntax from the repository root:

```sh
for file in knowledge/*.json; do
  python3 -m json.tool "$file" > /dev/null || exit 1
done
```

The booking service loads these JSON rule details at API startup and stores a
policy snapshot with each booking. Baggage pricing, changes, and cancellation
outcomes use that snapshot. `scripts/configure_elevenlabs.py` uploads all six
documents and attaches them to the agent for ElevenLabs-managed retrieval during
conversations. Rerun provisioning after policy changes. Retrieval runs in
ElevenLabs; the API uses the structured JSON rules directly.
