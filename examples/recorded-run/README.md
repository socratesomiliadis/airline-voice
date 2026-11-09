# Recorded autonomous refinement

This is a real ElevenLabs Chat Mode run against the fictional PostgreSQL airline,
recorded on November 7, 2026. The customer, evaluator and repair model roles use
separate calls. The complete thirteen-scenario suite covers all ten assessment
call types. The run passed in two iterations after one automatic prompt repair. The pass
threshold was 8 for every criterion; the iteration limit was 5. No backend patch
was needed in this particular recording.

The experiment used an isolated ElevenLabs branch. Its starting prompt deliberately
withheld booking references unless the customer requested them, creating a known
confirmation defect. This seeded defect is part of the experiment, not an
undisclosed failure in the normal system prompt. The evaluator also caught an
incorrect calculation of the pet policy's 48-hour notice period. The worker
diagnosed prompt failures, rewrote and published the prompt automatically, then
re-ran the whole suite. No human edited the prompt between evaluated iterations.

## Evidence

- [Starting prompt](initial-prompt.md): the exact provider prompt read at run start.
- [Final prompt](final-prompt.md): the prompt used in the final evaluated iteration.
- [Prompt diff](prompt.patch): the complete starting-to-final change.
- [Structured report](report.json): source run ID, timestamps, model roles,
  scenario definitions, actual per-criterion scores, failure quotes, root causes,
  repair explanations, tool evidence, saved booking states, and first-to-final
  score changes. Regressions are retained, not hidden by averages.

All customers and financial movements are fictional. Provider request headers,
debug events, environment configuration and source dumps are excluded. Known
credential values are redacted. Conversation IDs remain as provenance for the
private provider sessions. Full raw artifacts remain local and ignored.

## Reproduce

Follow the [first-time provider setup](../../docs/elevenlabs.md) using your own
credentials, API and database. For the seeded baseline, create a separate private
agent with:

```sh
uv run --all-packages python scripts/configure_elevenlabs.py --create-agent "Recorded assessment" --prompt-file examples/recorded-run/initial-prompt.md
```

Set `ELEVENLABS_AGENT_ID` to the printed ID, configure the model credentials, then
run `make refine`. The worker reads the remote starting prompt and automatically
saves a repaired prompt to its configured `prompt_path`. Use a dedicated checkout
or a separate prompt path when reproducing an experiment. New agents use provider
defaults; this report records the original model roles. Conversations and judge
scores are stochastic, so the number of iterations and exact wording can differ.

Export a completed run with:

```sh
uv run --all-packages python scripts/export_refinement_run.py artifacts/RUN_ID --output examples/recorded-run
```


## Limits of this recording

This historical report predates independent fixture selection references and the
current deterministic checks. It is preserved unchanged; newer fields have not
been backfilled as if they had been captured at the time. It demonstrates prompt
repair, not live backend fault diagnosis, database-gated code repair or reload.

The final basic-fare conversation incorrectly suggests that a booking created on
November 6 has probably passed its 24-hour window even though the demonstration
business time is November 6. Its understanding score of 10 is overgenerous. The
advance-purchase condition is a separate issue. The current factual regression
checks this exact recorded explanation and prevents a passing understanding score
with same-day purchase timestamps. Historical scores are not recalculated or
silently corrected in this report.

See [judge regression cases](../../evaluations/judge-calibration.json) for the
requester-labelled counterexample and four additional human-reviewed cases,
and [current assessment boundaries](../../docs/refinement.md#assessment-boundaries-and-production-work).


A [new live backend-repair recording](../backend-repair-run/README.md) demonstrates
actual model diagnosis, database-gated code repair, reload and a successful next
conversation. That newer recording also preserves its later failures and terminal
provider error; it is not labelled as a passing suite.
