# Session-close regression evidence

This full-suite attempt stopped during its fifth scenario, `cabin-pet`.
It is an error run, not a passing suite. The first four scenarios were evaluated;
rescheduling failed naturalness with a score of seven. The prompt was unchanged.

The pet conversation's authoritative transcript records a successful `end_call`
after the customer said they needed nothing else. The simulator then attempted
another customer message and reported `Unable to send ElevenLabs customer message`.
This exposed a session-close race, rather than a booking or policy API failure.
The pending pet request was captured and fixture cleanup completed.

The current adapter recognizes successful, unblocked system `end_call` results.
The simulator checks closure again after customer-model generation, and a send
that races with a normal connection close ends cleanly. Abnormal connection
closures still produce errors. Regression tests cover these cases.

This was a manual orchestration fix after the run stopped. It is not counted as an
autonomous repair or retroactively applied to this report. The full suite is rerun
from the beginning with fresh fixtures after the fix.

- [Report](report.json): actual partial evaluations, conversations, saved state,
  and the terminal error. Missing evaluations remain missing.
- [Starting prompt](initial-prompt.md), [final prompt](final-prompt.md), and
  [prompt diff](prompt.patch): no prompt changes occurred in this attempt.

All customers and financial movements are fictional. The portable export excludes
provider headers, debug events, environment settings, and source dumps, and
redacts known credentials.
