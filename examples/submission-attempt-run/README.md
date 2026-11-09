# Full-suite submission attempt

This attempt used the complete seventeen-scenario suite and the updated customer
instructions. It stopped before completing its baseline because ElevenLabs
rejected a new Chat Mode session with close code 3000:

> The AI agent you are trying to reach is not available.

It is an error run, not a passing suite. Four scenarios were evaluated; three
passed. The pet scenario never established a conversation. No automatic repair
was applied in this attempt, and no prompt was promoted to the main agent.

The failed rescheduling conversation is retained. The assistant quoted a zero
change fee and a 10 USD total before confirmation, but the correct backend
settlement was a 30 USD fee plus a 10 USD fare difference. The evaluator failed
understanding, API correctness, confirmation, and naturalness. This prompt failure
still needs a repair and a complete live reevaluation.

The starting prompt came from the automatic repair in the
[customer-goal regression run](../customer-goal-regression/README.md). The customer
instructions were manually clarified before this fresh attempt. The
[session-close regression](../session-close-regression/README.md) documents the
separate normal-closure bug fixed before both of these attempts. This close-code
3000 rejection is an abnormal provider failure and is still reported as an error.

Local API and public webhook readiness passed before the run. Separate signed
session diagnostics reproduced the rejection on both the main and test branches.
The configured key cannot read subscription details (`missing_permissions`).
A subsequent text-chat attempt in ElevenLabs Preview through Dia showed the
specific cause:

> [quota_exceeded] You've run out of credits. Add credits or upgrade your plan to start a new conversation.

This browser diagnosis does not change the original run's generic close-code
error or its missing evaluations. Credits must be restored before reevaluation.

- [Report](report.json): actual scenarios, partial scores, failure diagnoses,
  transcripts, booking state, and the terminal error. Missing scores remain null.
- [Starting prompt](initial-prompt.md), [final prompt](final-prompt.md), and
  [prompt diff](prompt.patch): the prompt was unchanged in this attempt.

Restore provider availability, then run the complete suite again using the
[refinement guide](../../docs/refinement.md). A full passing result is still
unverified. Earlier recordings remain separate evidence and must not be combined
into a passing seventeen-scenario run.

All customers, bookings, and financial movements are fictional. The export
excludes provider headers, URLs, debug events, environment settings, and source
dumps, and redacts known credentials.
