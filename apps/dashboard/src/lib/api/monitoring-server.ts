import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseEnv } from "node:util";

function configuration() {
  let workspace: Record<string, string | undefined> = {};
  try {
    // Local host setup shares the workspace secret; it never enters a client bundle.
    workspace = parseEnv(readFileSync(resolve(process.cwd(), "../../.env"), "utf8"));
  } catch {
    // Containers and deployments supply server-side environment variables directly.
  }
  return {
    base: process.env.API_BASE_URL || workspace.REFINER_API_BASE_URL || "http://localhost:8000",
    key: process.env.AGENT_API_KEY || workspace.AGENT_API_KEY || "",
  };
}

export async function forwardMonitoring(request: Request, streaming: boolean) {
  const { base, key } = configuration();
  const requestedRun = new URL(request.url).searchParams.get("run_id");
  if (requestedRun && !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$/.test(requestedRun)) {
    return Response.json({ error: "Invalid run selection" }, { status: 400 });
  }
  const target = new URL(
    `api/v1/monitoring/${streaming ? "events" : "snapshot"}`,
    `${base.replace(/\/$/, "")}/`,
  );
  if (requestedRun) target.searchParams.set("run_id", requestedRun);
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), 5_000);
  try {
    const upstream = await fetch(target, {
      headers: {
        "X-Agent-Api-Key": key,
        Accept: streaming ? "text/event-stream" : "application/json",
      },
      cache: "no-store",
      signal: AbortSignal.any([request.signal, timeout.signal]),
    });
    clearTimeout(timer);
    if (!upstream.ok) {
      await upstream.body?.cancel();
      return Response.json(
        { error: "Monitoring is temporarily unavailable" },
        {
          status: upstream.status === 404 ? 404 : 503,
        },
      );
    }
    return new Response(upstream.body, {
      headers: {
        "Content-Type": streaming ? "text/event-stream; charset=utf-8" : "application/json",
        "Cache-Control": "no-store, no-transform",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    return Response.json({ error: "Monitoring is temporarily unavailable" }, { status: 503 });
  } finally {
    clearTimeout(timer);
  }
}
