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

`sources/` remains an ignored local drop location for future source documents.
The policy JSON files are outside that ignored directory so they can be version controlled.
Loading, parsing into domain models, indexing, retrieval, and provider upload are
not implemented.
