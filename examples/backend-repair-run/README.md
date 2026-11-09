# Live backend repair and diagnostic evidence

This is a real ElevenLabs/Anthropic run against the fictional PostgreSQL service,
recorded November 8, 2026 (Pacific time). It is an **error run, not a passing suite**.
The complete evidence includes one diagnostic baseline, one complete seventeen-scenario
iteration, and a partial third iteration interrupted by a provider message-send failure.
The failed conversations and rejected repair have not been removed.

The experiment deliberately inserted an unconditional `RuntimeError` at the start
of `BookingService._cancel`. This is a disclosed, simple seeded fault in an otherwise
working endpoint. It does not demonstrate discovery of an unseeded or subtle backend bug.
An isolated agent branch was used. The public development tunnel was restored before
this recording; all customers, bookings and financial movements are fictional.

## What the backend sequence establishes

The first conversation reached a valid cancellation request and received server errors.
Fixture cleanup independently reproduced HTTP 500 while health and database readiness
passed. The worker retained the transcript and application-failure evidence, evaluated
it, and asked the real repair model for a code fix. It stopped creating fixtures until
cleanup could be recovered.

The model identified `BookingService._cancel` and removed the injected line. The actual
PostgreSQL verification gate passed all 32 required database tests, the real local reload
helper restarted the API, database readiness succeeded, and the pending fixture was
cleaned up. No verification adapter or scripted model response was substituted.
The next fresh provider conversation successfully cancelled its new booking, and all
its deterministic checks passed. **The system prompt was unchanged by this repair.**

The second iteration completed all seventeen scenarios. All thirteen original scenarios
passed, including the independent fixture checks for earliest and cheapest selection.
The new withdrawn-consent scenario passed. The other three new interaction scenarios
failed: airport drift after a date correction, an unsupported claim that unavailable
business inventory meant a cabin did not exist, and incorrect policy reasoning.
These are real observed limitations, not seeded conversational defects.

## Why the run did not pass

The subsequent prompt-repair request exceeded the model context limit because it included
all simulations, duplicate streaming dialogue, debug events and passing checks. The
worker rejected that repair and left the prompt unchanged. During the next iteration,
ElevenLabs failed to send a customer message in the pet scenario; the run stopped with
its error and partial evaluations intact. Neither baseline nor final suite is marked
complete. Only the second iteration is a complete suite; missing first/final scenario
scores remain null.

The current proposer sends authoritative evidence only for actionable failed scenarios,
omits duplicate dialogue/debug events and passing checks, and keeps the full original
artifacts. A separate read-only probe using this run's complete seventeen-scenario
iteration produced a validated real model proposal with the reduced payload. That probe
was **not activated** and is not retroactively counted as a repair in this recording.
The actual context rejection and later provider failure remain in `report.json`.

## Files

- [Structured report](report.json): actual evaluations, deterministic checks, fixture
  references and hashes, business clock, transcripts, persisted bookings, repair status,
  source hashes, verification receipts, cleanup recovery and terminal error.
- [Injected fault](experiment.json) and [actual code patch](code.patch).
- [Activation evidence](backend-activation.json): actual verification receipt, reload
  helper output, recovered fixture and first post-reload provider conversation ID.
- [Current checker replay](current-check-replay.json): read-only replay over the exported
  evidence, with hashes of the checker files. Original scores and checks are unchanged.
- [Reduced repair payload probe](repair-payload-probe.json): validated, unactivated proposal receipt.
- [Starting prompt](initial-prompt.md), [final prompt](final-prompt.md) and [prompt diff](prompt.patch).

The portable export preserves request IDs, fixture state and independent selection
references so checks can be replayed. It excludes provider debug events, headers,
arbitrary environment configuration and source dumps. Known credential values are
redacted. Conversation IDs remain provenance for private provider sessions.

To export an error run explicitly, preserving its incomplete status:

```sh
uv run --all-packages python scripts/export_refinement_run.py artifacts/RUN_ID \
  --output examples/backend-repair-run --include-incomplete
```

The normal exporter still rejects error runs unless that flag is supplied. Do not
relabel this report as passing or backfill missing evaluations. See
[assessment boundaries](../../docs/refinement.md#assessment-boundaries-and-production-work)
and [human-labelled policy cases](../../evaluations/README.md).


A separate [focused interaction run](../interaction-repair-run/README.md) subsequently
used the reduced repair payload in the normal loop. It automatically repaired its
prompt and passed all four harder scenarios on reevaluation. That scoped result
does not replace this run's error status or establish a complete seventeen-scenario
pass under the new prompt.
