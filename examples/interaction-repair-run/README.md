# Live interaction-regression repair

This real ElevenLabs/Anthropic run exercises the four newly added interaction
scenarios against the fictional PostgreSQL service. It passed all four scenarios
in its second iteration after one automatic prompt repair. No backend code was
changed. The run used the same isolated agent branch as the backend experiment,
reset to the repository's starting prompt before the first conversation.

The baseline failed the ambiguous-date comparison, unavailable-inventory interaction
and policy-reasoning challenge. Withdrawn consent already passed. The real repair
model received the failed scenarios' authoritative evidence with streaming duplicates
and passing checks omitted. The worker validated and published its rewritten prompt,
then reran all four scenarios. Every final deterministic check and every score
criterion passed. Full baseline failures, final results and prompt changes are retained.

This is a focused four-scenario result. The thirteen original scenarios were not
rerun under this new prompt, so it does not establish a passing seventeen-scenario
suite or justify a production rollout. The repository's default prompt and the main
agent's prompt were not replaced by this experiment; the tested candidate is available
here for review. The full backend experiment remains an error run and has not been
relabeled because this separate focused run passed.

- [Report](report.json): actual provider conversations, checks, scores, failures,
  fixture state, repair proposal and activation status.
- [Starting prompt](initial-prompt.md), [tested candidate](final-prompt.md), and
  [complete prompt diff](prompt.patch).
- [Backend experiment](../backend-repair-run/README.md): real code diagnosis,
  database gate, reload and subsequent cancellation, with later errors preserved.
- [Human-labelled policy cases](../../evaluations/README.md) and
  [scope and production boundaries](../../docs/refinement.md).

Customers, bookings and financial movements are fictional. Credentials, provider
headers, debug events, source dumps and environment configuration are excluded.
Conversation IDs remain as provenance for private provider sessions.

Reproduce using the four named scenarios in `scenarios/airline.json`, a dedicated
agent branch and prompt path, the configured demo business clock, and the normal
refinement runner. The terminal limit was two iterations with a passing threshold
of eight for every criterion. Exact dialogue and scores are stochastic.
