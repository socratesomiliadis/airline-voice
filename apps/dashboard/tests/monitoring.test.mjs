import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function load(source) {
  const input = await readFile(new URL(source, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(input, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}
const { minimumScores, passedCount, diffLines } = await load(
  "../src/features/monitoring/format.ts",
);
const { forwardMonitoring } = await load("../src/lib/api/monitoring-server.ts");
const scores = (understanding = 9) => ({
  understanding,
  api_correctness: 9,
  outcome_confirmation: 9,
  naturalness: 9,
});

test("one low criterion stays visible rather than disappearing in an average", () => {
  const iteration = {
    scenarios: [
      { evaluation: { scores: scores(3) } },
      { evaluation: { scores: scores(10) } },
      { evaluation: null },
    ],
  };
  assert.equal(minimumScores(iteration).understanding, 3);
  assert.equal(passedCount(iteration, 8), 1);
  assert.equal(minimumScores({ scenarios: [{ evaluation: null }] }), null);
});

test("diff keeps old/new line numbers and separates metadata from changes", () => {
  const lines = diffLines("--- before\n+++ after\n@@ -3,2 +3,3 @@\n same\n-old\n+new\n+another\n");
  assert.equal(lines.filter((line) => line.kind === "added").length, 2);
  assert.equal(lines.filter((line) => line.kind === "removed").length, 1);
  assert.deepEqual(
    lines.find((line) => line.text === "same"),
    {
      id: "3: same",
      text: "same",
      kind: "context",
      before: 3,
      after: 3,
    },
  );
  assert.equal(lines.find((line) => line.text === "old").before, 4);
  assert.equal(lines.find((line) => line.text === "another").after, 5);
});

test("the observation proxy sends a server-only credential and preserves streaming", async () => {
  const originalFetch = globalThis.fetch;
  const originalBase = process.env.API_BASE_URL;
  const originalKey = process.env.AGENT_API_KEY;
  process.env.API_BASE_URL = "http://airline.test:8000";
  process.env.AGENT_API_KEY = "private-observation-key";
  let cancelled = false;
  let input;
  globalThis.fetch = async (url, options) => {
    input = { url, options };
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode('event: snapshot\ndata: {"runs":[],"run":null}\n\n'),
        );
      },
      cancel() {
        cancelled = true;
      },
    });
    return new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
  };
  try {
    const response = await forwardMonitoring(
      new Request("http://dashboard.test/api/monitoring?run_id=run-1"),
      true,
    );
    assert.equal(
      input.url.toString(),
      "http://airline.test:8000/api/v1/monitoring/events?run_id=run-1",
    );
    assert.equal(input.options.headers["X-Agent-Api-Key"], "private-observation-key");
    assert.equal(input.options.cache, "no-store");
    assert.equal(response.headers.get("Content-Type"), "text/event-stream; charset=utf-8");
    assert.equal(response.headers.get("X-Agent-Api-Key"), null);
    const reader = response.body.getReader();
    const first = new TextDecoder().decode((await reader.read()).value);
    assert.match(first, /event: snapshot/);
    assert.doesNotMatch(first, /private-observation-key/);
    await reader.cancel();
    assert.equal(cancelled, true);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalBase === undefined) delete process.env.API_BASE_URL;
    else process.env.API_BASE_URL = originalBase;
    if (originalKey === undefined) delete process.env.AGENT_API_KEY;
    else process.env.AGENT_API_KEY = originalKey;
  }
});

test("invalid selections never become arbitrary upstream paths", async () => {
  const response = await forwardMonitoring(
    new Request("http://dashboard.test/api/monitoring?run_id=..%2Fother"),
    false,
  );
  assert.equal(response.status, 400);
});

test("backend failures become a reconnectable error without leaking upstream content", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response("internal secret detail", { status: 401 });
  try {
    const response = await forwardMonitoring(
      new Request("http://dashboard.test/api/monitoring"),
      true,
    );
    assert.equal(response.status, 503);
    assert.doesNotMatch(await response.text(), /internal secret detail/);
  } finally {
    globalThis.fetch = original;
  }
});
