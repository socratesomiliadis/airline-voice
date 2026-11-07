# Autonomous refinement

The Python worker runs the complete cycle without interactive approvals:

1. For every scenario, create fresh prerequisite bookings through the airline API.
   A customer LLM chats with the existing ElevenLabs airline assistant over its
   authenticated WebSocket, with `conversation.text_only=true`. No audio is sent.
2. Close the chat and retrieve ElevenLabs' authoritative transcript, including
   tool calls, exact arguments and tool results. Capture persisted booking state
   before cancelling test bookings to release inventory.
3. A separate, stateless evaluator LLM call scores understanding, API correctness,
   outcome confirmation and naturalness from 1–10. Each failed criterion must
   have an actual evidence quote, explanation and `prompt` or `code` root cause.
   Backend errors are distinguished from valid rejection of bad agent arguments.
4. A repair LLM rewrites the complete system prompt for prompt failures and
   proposes exact-text Python edits for code failures. Both can occur together.
5. Automatically apply bounded code edits, compile the changed modules, run the
   configured regression command, reload the API, and wait for database-backed
   readiness. Publish a changed prompt using ElevenLabs' REST `PATCH` endpoint,
   and save it to `prompts/agent/system.md` after publication succeeds.
6. Repeat the **entire** suite. Stop when every criterion of every scenario is
   at least 8, or after 5 evaluated iterations (including the initial baseline).
   There is no final, unevaluated repair after the limit is reached.

`PASS_SCORE` and `MAX_ITERATIONS` in the worker's `config.py` define the defaults;
TOML and CLI options override them. A high average cannot hide a failing criterion.

## Running

Run the worker **on the host from the repository root**. The refiner container
currently supports CLI inspection; its read-only mounts do not support source
patching or host process management.

Use the existing development API and database. Check for listeners before
starting either service. If needed, follow the README's database migration and
flight seeding steps and start the API with `make dev-api`. Ensure the ElevenLabs
agent's webhook URLs point at this API (including a working public HTTPS tunnel
for a local API), with the matching `AGENT_API_KEY`. Agent provisioning is covered
in [ElevenLabs setup](elevenlabs.md).

Configure `.env`:

```dotenv
ELEVENLABS_API_KEY=...
ELEVENLABS_AGENT_ID=...
AGENT_API_KEY=...
REFINER_MODEL_API_KEY=...
REFINER_MODEL_BASE_URL=https://api.openai.com/v1
REFINER_API_BASE_URL=http://localhost:8000
REFINER_CONFIG_PATH=config/refinement.example.toml
REFINER_ARTIFACTS_DIR=artifacts
SIMULATION_NOW=2026-11-06T12:00:00Z
```

`OPENAI_API_KEY` is a fallback when `REFINER_MODEL_API_KEY` is absent. The model
endpoint must implement Chat Completions and strict JSON Schema structured output.
Customer, evaluator and repair models are independently configurable in TOML;
they default to `gpt-4.1-mini`, `gpt-4.1` and `gpt-4.1`. Their messages and histories
are separate; the evaluator receives evidence, never the customer's hidden reasoning.

```sh
uv sync --all-packages --frozen
uv run --package airline-refiner airline-refiner run
```

If `uv` is installed only in this checkout's `.tools/bin`, add that directory to
`PATH` first so configured verification/reload commands can find it:

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

`editable_roots` defaults to `apps/api/src/airline_api`. Existing Python modules
and new helper modules inside those roots can change. The worker rejects absolute
paths, traversal, symlinks, stale source, ambiguous replacements, invalid Python,
and patches exceeding `max_patch_files`. Tests, scenarios, policies and the
refiner itself are outside the default editable paths. Model-generated shell
commands are never executed; commands come only from the trusted TOML config.
The workspace lock prevents concurrent runs from patching the same checkout.

The default verification command is `uv run --all-packages pytest -q`. Set
`TEST_DATABASE_URL` in the worker's **environment** to include PostgreSQL
regressions; those tests create and drop their own disposable databases. Without
it, database integration tests are skipped. Verification runs on the host before
service reload, so dependencies for all workspace packages must be installed.

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
an execution sandbox. Backend API refinement/monitoring HTTP endpoints and live
dashboard integration remain separate work. Run artifacts are local JSON files.

## Scenarios and artifacts

`scenarios/airline.json` contains eight fictional fixtures: booking, cancellation,
rescheduling, checked baggage, cabin pets, mobility assistance, check-in policy,
and basic-fare change restrictions. Each includes a customer goal/facts, required
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

Each run writes `artifacts/<run-id>/run.json`, the resolved nonsecret config,
scenario snapshots, original prompt, and iteration directories containing:

- `<scenario>.simulation.json`: conversation ID, dialogue, full transcript, tool
  events, fixture, persisted booking state, and execution/cleanup errors.
- `<scenario>.evaluation.json`: four scores, rationale, failure quotes, root
  causes and relevant source paths.
- `prompt.md` and `source.json`: the prompt and source used in that iteration.
- `repair.json`, `code.patch`, verification/reload logs when a repair is attempted.

Provider transport, malformed model output and evidence validation have bounded
retries. Customer turns, per-turn waiting, transcript processing, subprocesses
and readiness each have configurable limits. Failed or incomplete conversations
cannot silently become a passing run.

## Provider references

- [ElevenLabs Chat Mode](https://elevenlabs.io/docs/eleven-agents/guides/chat-mode)
- [ElevenLabs WebSocket events](https://elevenlabs.io/docs/eleven-agents/api-reference/eleven-agents/websocket)
- [Conversation/tool transcripts](https://elevenlabs.io/docs/api-reference/conversations/get)
- [Agent REST updates](https://elevenlabs.io/docs/api-reference/agents/update)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat)
