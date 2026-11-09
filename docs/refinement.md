# Autonomous refinement

The Python worker runs the complete cycle without interactive approvals:

1. For every scenario, create fresh prerequisite bookings through the airline API.
   A customer LLM chats with the existing ElevenLabs airline assistant over its
   authenticated WebSocket, with `conversation.text_only=true`. No audio is sent.
2. Close the chat and retrieve ElevenLabs' authoritative transcript, including
   tool calls, exact arguments and tool results. Capture persisted booking state
   before cancelling test bookings to release inventory. Next/cheapest scenarios
   also calculate an independent reference from the trusted flight fixture before
   the conversation, recording its hash, query, business clock and all optimal ties.
3. A separate, stateless evaluator LLM call scores understanding, API correctness,
   outcome confirmation and naturalness from 1–10. Each failed criterion must
   have an actual evidence quote, explanation and `prompt`, `code` or `infrastructure`
   root cause. Infrastructure diagnoses are retained but do not trigger prompt rewrites
   or code edits without a separately reproduced application failure.
   Each code failure identifies its existing file, qualified function, and the
   faulty behavior versus expected behavior. Backend errors are distinguished
   from valid rejection of bad agent arguments. Deterministic checks independently
   validate successful tools, correct references/quotes/passengers, dates, seat
   requests, item quantities/measurements/fees, ledger totals and forbidden writes.
   Explicit `assertions` in the scenario JSON define expected state and tool order.
   Failed checks require grounded API/outcome failure diagnoses from the judge;
   high model scores cannot override them. Correct recovery from a tool error is
   allowed when a later call succeeds and persisted outcomes match.
4. A repair LLM rewrites the complete system prompt for prompt failures and
   proposes exact-text Python edits to the diagnosed functions for code failures.
   It receives those files and behavior diagnoses, the authoritative transcripts and
   persisted state for failed scenarios, and all evaluation scores/diagnoses. Passing
   checks, raw debug events and duplicate streaming dialogue are omitted from the
   repair request; complete evidence remains in artifacts. Both fix types can occur together.
5. Automatically apply bounded code edits, compile the changed modules, run the
   configured regression command, reload the API, and wait for database-backed
   readiness. Publish a changed prompt using ElevenLabs' REST `PATCH` endpoint,
   and save it to `prompts/agent/system.md` after publication succeeds.
6. Repeat the **entire** suite. Stop when every criterion of every scenario is
   at least 8, or after 5 evaluated iterations (including the initial baseline).
   There is no final, unevaluated repair after the limit is reached.

`PASS_SCORE` and `MAX_ITERATIONS` in the worker's `config.py` define the defaults;
TOML and CLI options override them. A high average cannot hide a failing criterion.
A failed deterministic outcome check also prevents passing, even at threshold 1.

## Running

When `PUBLIC_API_BASE_URL` is configured, CLI execution checks its authenticated
readiness before any model calls or conversations. A dead public tunnel must be
restored even when localhost is healthy. Judges can also classify external webhook
failures during a conversation as `infrastructure`; the runner preserves that
diagnosis and stops repair rather than asking the prompt fixer to cure an outage.

Run the worker **on the host from the repository root**. The refiner container
currently supports CLI inspection; its read-only mounts do not support source
patching or host process management.

Use the existing development API and database. Check for listeners before
starting either service. If needed, follow the README's database migration and
flight seeding steps and start the API with `make dev-api` (without `--reload`). The worker checks the
existing service before simulation and before writing a backend patch. Watched
services are rejected; `make dev-api-watch` is only for interactive editing. Ensure the ElevenLabs
agent's webhook URLs point at this API (including a working public HTTPS tunnel
for a local API), with the matching `AGENT_API_KEY`. Agent provisioning is covered
in [ElevenLabs setup](elevenlabs.md).

Configure `.env`:

```dotenv
ELEVENLABS_API_KEY=...
ELEVENLABS_AGENT_ID=...
AGENT_API_KEY=...
ANTHROPIC_API_KEY=...
REFINER_MODEL_BASE_URL=https://api.anthropic.com/v1
REFINER_API_BASE_URL=http://localhost:8000
REFINER_CONFIG_PATH=config/refinement.example.toml
REFINER_ARTIFACTS_DIR=artifacts
SIMULATION_NOW=2026-11-06T12:00:00Z
```

`REFINER_MODEL_API_KEY` can supply an Anthropic key when `ANTHROPIC_API_KEY` is
absent. The worker calls Anthropic's native Messages API with `x-api-key` and
`anthropic-version: 2026-10-21`, using `output_config.format` for JSON Schema output.
`OPENAI_API_KEY` is no longer used. Any custom `REFINER_MODEL_BASE_URL` must implement
the Anthropic Messages contract; remove an old OpenAI endpoint override when migrating.
Customer, evaluator and repair models are independently configurable in TOML;
they default to `claude-haiku-5-5`, `claude-sonnet-5-5` and `claude-sonnet-5-5`.
`model_max_tokens` defaults to 16384 per call; increase it if a repair reaches the
output limit. Unsupported schema constraints are sent as field descriptions and
enforced locally by Pydantic, alongside evidence validation. Each role keeps its
messages and history separate; the evaluator receives evidence, never the customer's
hidden reasoning.

```sh
uv sync --all-packages --frozen
make refine
```

`make refine` puts this checkout's `.tools/bin` on `PATH` for the worker and its
verification/reload subprocesses. When invoking the CLI directly, add it first:

```sh
export PATH="$PWD/.tools/bin:$PATH"
```

Override limits or use a different config:

```sh
uv run --package airline-refiner airline-refiner run \
  --config config/refinement.example.toml --pass-score 9 --max-iterations 3
```

Exit codes are `0` for a passing suite, `1` for iteration exhaustion and `2` for
configuration, provider or unrecoverable execution errors. Missing credentials
fail before network calls or mutations. HTTP credentials and known secrets are
redacted from artifacts; signed WebSocket URLs are never logged.

## Repairs and service reload

`editable_roots` defaults to `apps/api/src/airline_api`. Patches change specific
existing functions inside the evaluator's diagnosed files. Each code diagnosis
contains `path`, `function` (for example `BookingService.cancel`) and `behavior`.
The fixer must name that same path/function in each edit; exact replacements
are scoped to that function, preserving the rest of the file. An AST check rejects
changes to unrelated functions or module-level code. New files, function renames
and arbitrary refactors are outside this contract. The worker also rejects absolute
paths, traversal, symlinks, stale source, ambiguous replacements, invalid Python,
and patches exceeding `max_patch_files`. Tests, scenarios, policies and the
refiner itself are outside the default editable paths. Model-generated shell
commands are never executed; commands come only from the trusted TOML config.
The workspace lock prevents concurrent runs from patching the same checkout.

Backend repairs require `TEST_DATABASE_URL` in the worker environment or root
`.env`. Use a PostgreSQL role with `CREATE DATABASE`: fixtures create and drop
random disposable databases and do not reset the airline database. The worker
rejects missing/non-PostgreSQL configuration before writing candidate source.

The default command remains `uv run --all-packages pytest -q`. The worker injects
a pytest verification plugin and a fresh receipt nonce. `required_database_tests`
in TOML identifies the required booking, migration and fixture-lifecycle groups.
Every required test must be collected, use the PostgreSQL fixture, and pass setup,
call and teardown. Skips, xfails, deselection, missing groups, stale receipts and
commands that return success without a valid receipt all prevent activation.
The receipt is saved as `verification.json`. Other optional offline tests may
still skip outside those required groups. Custom verification commands must also
run the plugin and produce a passing receipt; they cannot authorize reload by
exit status alone. A failed check restores candidate source before recovery.

Run the same strict gate directly (it loads the root `.env`):

```sh
make verify-backend
```

Verification runs on the host before service reload, so install all workspace
packages and development dependencies. CI uses this strict gate with PostgreSQL.

The default reload helper checks for an existing listener. For the local airline
Uvicorn process it saves its launch command, terminates that specific service,
waits for the port to be free and relaunches it. For an existing Compose API
container it rebuilds and replaces that container. It refuses unrelated local
processes and never starts a second server on an occupied port. Local service logs
and restart argv are kept under `artifacts/service/`. Non-local services require
an explicit `reload_command`, for example an existing deployment's restart tool.

On failed checks, reload, readiness or prompt publication, the worker restores
original source and prompt, reloads the restored service, records the error and
tries again within the remaining iteration budget. Verification/reload log excerpts
are supplied to subsequent repair calls. If recovery fails, the run stops with an
error instead of continuing against an unknown version.

Code is applied and checked in the configured development checkout; this is not
an execution sandbox. The [read-only observation dashboard](monitoring.md) streams live progress, scores,
changes and history from the local artifacts. Backend refinement-control endpoints
remain reserved; the UI exposes no commands.

## Scenarios and artifacts

`scenarios/airline.json` contains seventeen fictional fixtures covering all ten
assessment call types plus booking and policy regressions. See
[the coverage mapping](../scenarios/README.md). Each includes a customer goal/facts, required
tools, expected outcome, and optional prerequisite booking specification. All
iterations use new passenger/action IDs, and successful cleanup releases seats
without deleting audit history. Simulation and cleanup errors prevent passing
API/outcome scores. The November fixture week needs the fixed business clock
shown above once those departures would otherwise be in the past.

Add scenarios to that JSON file or change `scenarios_path`. IDs must be unique
and filename-safe. The suite cannot be empty. Required tools must actually have
been executed, rather than merely mentioned by the assistant. The evaluator also
checks ordering, arguments, outcomes and policy facts against source, the full
transcript, persisted state and `knowledge/*.json`.

Each run writes a self-contained `artifacts/<run-id>/run.json` plus a live redacted
`monitor.json`. The aggregate report contains timestamps, configuration, scenario
contracts, starting/final prompts, backend source hashes, every simulation and
evaluation (including deterministic checks), complete repair proposals and reasons,
prompt/code diffs, application/rollback status, verification receipts and bounded
execution-log excerpts. `performance_summary` records initial/final scores and
per-criterion changes for each scenario. `baseline_complete` and `final_complete`
identify partial runs; an untested scenario has null scores/deltas, never invented
improvement. `deployment_consistent=false` identifies unrecoverable deployment
state, and its final prompt/source metadata are marked unknown.

`final-prompt.md` is also written separately. Every iteration is finalized to
`iteration.json`, including the terminal passing/limit iteration and interrupted
or failed iterations. Further evidence files include:

- `<scenario>.simulation.json`: conversation ID, dialogue, full transcript, tool
  events, fixture, persisted booking state, and execution/cleanup errors.
- `<scenario>.evaluation.json`: four scores, rationale, failure quotes, root
  causes and precise file/function/behavior diagnoses for code failures.
- `prompt.md` and `source.json`: the prompt and source used in that iteration.
- `repair.json`, `code.patch`, verification receipts and verification/reload logs
  when a repair is attempted. Log excerpts in the aggregate report are capped at
  12,000 characters per command; complete command logs remain alongside it.

Provider transport, malformed model output and evidence validation have bounded
retries. Customer turns, per-turn waiting, transcript processing, subprocesses
and readiness each have configurable limits. Failed or incomplete conversations
cannot silently become a passing run.
Provider, authentication, transport, and unclassified fixture failures stop before
repair. A repeatable application endpoint failure takes a separate diagnostic path:
read requests and mutations carrying a durable idempotency key are replayed once.
If both responses have the same 5xx status and authenticated `/ready` plus `/health`
probes succeed, the worker records `application_failures` with the stage, request
method/path, status and reproduction evidence. A single pooled-connection close
can be retried for reads/keyed mutations; arbitrary writes are never replayed.
`/ready` queries seeded database tables directly and reports the service business
clock; it does not call the booking/search implementation under repair.

These failures reach the evaluator even if preparation prevented a conversation.
They are candidates for application diagnosis, not proof of a particular source
fault: the evaluator must still locate the faulty function and distinguish an
invalid fixture from backend behavior. They cannot pass deterministic checks.
Missing evidence is retained as missing; it is never replaced with a fabricated
conversation. An external dependency used by just one endpoint can still require
operator investigation; healthy probes do not prove every dependency is healthy.

A failed cleanup sets `cleanup_pending`; the worker stops creating further fixtures,
diagnoses the available evidence, and attempts repair through the normal database
gate/reload sequence. It retries outstanding cleanup before starting the next
iteration. If cleanup still fails, the run stops and retains the caller/fixture
for recovery. At the final iteration limit it records unresolved cleanup without
claiming a passing run. Failed preparation/evidence collection can also be diagnosed
when they carry this reproduction evidence; other incomplete sessions cannot
trigger prompt rewrites or backend patches. ElevenLabs close code 3000 is reported
as an unavailable agent; check provider availability and account status before retrying.

## Provider references

- [ElevenLabs Chat Mode](https://elevenlabs.io/docs/eleven-agents/guides/chat-mode)
- [ElevenLabs WebSocket events](https://elevenlabs.io/docs/eleven-agents/api-reference/eleven-agents/websocket)
- [Conversation/tool transcripts](https://elevenlabs.io/docs/api-reference/conversations/get)
- [Agent REST updates](https://elevenlabs.io/docs/api-reference/agents/update)
- [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic models](https://platform.claude.com/docs/en/models/overview)

Custom `reload_command` implementations must enforce the same activation boundary:
running services must not watch candidate source while verification is in progress.
The bundled local/Compose helper checks this automatically.

Completed live runs can be exported using `scripts/export_refinement_run.py`.
The export preserves actual scores and diagnoses, including regressions.

The exporter accepts either a run directory or its standalone `run.json`. New
reports need no prompt, scenario or repair sidecar files to produce the portable
bundle. Older recorded examples remain readable through the legacy sidecar path.


## Independent selection and factual checks

`reference_dataset_path` selects trusted fixture JSON (default
`data/flights/week_2026_11_09.json`). The oracle imports no API search or booking
implementation. It filters schedule status, future departures, local date bounds,
route, cabin, fare tier, available seats, passenger count and price bounds, then
computes the minimum departure or price. All objective ties are accepted. The
checker recomputes the answer from the trusted file; agreement with a saved REST
offer alone cannot pass. Dataset ID/hash, business time, query, eligible count and
optimal offers are preserved in the simulation and portable export.

This is a **fixture oracle**, not a live inventory oracle. Use a dedicated database
seeded from the configured dataset and prevent external inventory writers. Changed
fares, schedule or stock require an independently captured trusted snapshot and a
new reference file. Do not use shared search output to refresh the oracle. This
assumption can produce failures when inventory drifts; it must not be hidden by
accepting the API's own answer. The assistant continues to use live API offers.

Policy checks have their own affected score criteria. The elapsed-cancellation
check blocks passing understanding when the assistant claims the 24-hour window
has expired without timestamps establishing more than 24 hours since purchase.
It catches the reported wording in the original recording, including its deferred
reference to "that window". This is a narrow language guard, not a complete
semantic policy verifier. The judge also receives the business clock and explicit
instructions to assess each explanation and distinguish elapsed purchase time
from the separate advance-purchase rule.

`evaluations/judge-calibration.json` contains the requester-labelled recorded
counterexample and four authored policy regression cases. The requester reviewed
and confirmed all four additional judgments in this session. All five now carry
human labels and explicit provenance. This remains a small policy-only calibration set. Run the raw
judge independently of deterministic score enforcement:

```sh
uv run --all-packages python scripts/calibrate_judge.py \
  --output artifacts/judge-calibration.json
```

The report retains label provenance, expected/observed decisions, raw scores,
explanations and factual checks. Expand and independently label policy reasoning,
confirmation accuracy, recovery and verbosity examples before using judge scores
as a conversational-quality release criterion.

## Assessment boundaries and production work

The original committed recording demonstrates a seeded prompt repair. Scripted
mixed-repair tests verify orchestration; they do not establish live model debugging
ability. Current runs must preserve deterministic checks, independent references,
source hashes, actual code patches, database verification receipts and subsequent
conversations before a backend-repair improvement claim is warranted. Keep older
recordings unchanged and identify seeded faults plainly. A partial diagnostic
baseline is not a complete suite baseline, and missing scores remain null.

Generated Python executes in the development checkout with the worker's host
permissions. Function-scoped patch validation and the PostgreSQL gate limit changes
but do not isolate execution. Production activation needs a separate disposable
checkout/container, restricted credentials/network access, independent verification
and a separate deployment boundary. Do not give model-generated code production
credentials or direct production deployment authority.

The shared agent API key authenticates an integration, not the customer. Caller IDs,
passenger IDs and possession of a booking reference do not establish booking
ownership. Customer identity verification and authorization on every booking read
and mutation remain production work.

Baggage additions and reschedules still need backend-generated, expiring cost
previews bound to the booking version, exact requested action and customer consent.
The current exact flight price/idempotency checks do not bind consent to the full
baggage fee or reschedule settlement. Financial movements remain simulated.

There are per-call/turn/iteration timeouts and a checkout lock, but no aggregate
spend ceiling or crash-safe transaction journal for the whole repair/deployment
cycle. Add provider usage budgets, durable recovery and startup reconciliation of
pending fixtures/source/prompt/deployment state. The local restoration path is
best-effort recovery inside a running process, not crash recovery.

Artifacts contain fictional transcripts, booking state and conversation IDs. Known
secrets are redacted; retention, access control, deletion across local/provider
storage and production PII handling are not implemented. Production deployment
needs those controls and separate test/production databases and agents.


The [live backend-repair recording](../examples/backend-repair-run/README.md)
contains a real model code fix, actual PostgreSQL receipt, service reload, recovered
cleanup and a successful next cancellation. It also retains three interaction
failures, a context-limit rejection and a later provider disconnect. It is explicitly
an error run, not a passing-suite claim. `--include-incomplete` allows that evidence
to be exported with errors, incomplete flags and missing evaluations preserved;
normal export still requires a completed run. The original prompt-only recording
remains unchanged.


A subsequent [focused interaction run](../examples/interaction-repair-run/README.md)
used the reduced repair payload, automatically repaired its prompt and passed the
four new scenarios in its second iteration. This is a scoped regression result;
the complete seventeen-scenario suite was not rerun under that candidate prompt.
The candidate remains on the isolated experiment branch and in the exported files.
