# Customer-goal regression evidence

This run completed one seventeen-scenario iteration and part of a second before
it was manually interrupted. It is an error run, not a passing suite. The first
iteration passed nine scenarios. The loop automatically revised and published
the prompt before starting the second iteration.

In the second iteration, the simulated pet customer repeatedly declined to
submit a request, despite its assigned facts requiring explicit confirmation of
submission. The assistant correctly respected the refusal. The outcome checker
failed the missing request, and the judge classified it as a prompt failure while
acknowledging the customer behavior. This is not evidence that the assistant
should have submitted without consent.

The run was interrupted before another repair to prevent that invalid customer
trajectory from driving a prompt change. Its partial final iteration and missing
scores remain visible. The original data and judgments are unchanged.

The current customer instructions explicitly prohibit invented refusals or
additional approval requirements when the scenario asks to submit a pending
request. Scenarios that require refusal, interruption, or withdrawn consent still
require those behaviors. This is a manual test-driver correction, not an
autonomous repair. Generated customer behavior remains stochastic and requires
inspection; the new instructions do not provide deterministic goal enforcement.

- [Report](report.json): the complete baseline, automatic prompt repair, partial
  second iteration, customer refusal, and interruption.
- [Starting prompt](initial-prompt.md), [refined prompt](final-prompt.md), and
  [prompt diff](prompt.patch): the actual automatic change before interruption.

All customers and financial movements are fictional. The export excludes provider
headers, debug events, environment settings, and source dumps, and redacts known
credentials. This run must not be combined with later results as one passing run.
