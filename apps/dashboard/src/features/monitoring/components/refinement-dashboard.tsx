"use client";

import {
  ArrowLeft,
  ArrowRight,
  CheckCheck,
  CircleAlert,
  FileCode2,
  History,
  ListChecks,
  MessagesSquare,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { dateTime, relative, scenarioName } from "@/features/monitoring/format";
import { useMonitoring } from "@/features/monitoring/monitoring-provider";
import { needsAttention, resolveObservation } from "@/features/monitoring/selection";
import { ChangeDiff } from "./change-diff";
import { ConversationFeed } from "./conversation-feed";
import { IterationHistory } from "./iteration-history";
import { RunOverview, WaitingForRun } from "./run-overview";
import { EvaluationDetails, ScenarioResults } from "./scenario-results";
import { ScorePanel } from "./score-panel";
import { StatusBadge } from "./status-badge";

export type EvaluationTab = "results" | "changes" | "history";
type View = "overview" | "conversations" | "evaluations";
const headings = {
  overview: {
    title: "Agent overview",
    description: "The health of your airline assistant, at a glance.",
  },
  conversations: {
    title: "Conversations",
    description: "Follow the conversation. Inspect the decisions behind it.",
  },
  evaluations: {
    title: "Evaluations",
    description: "Find quality gaps and trace the improvements that follow.",
  },
};
const tabs = [
  { id: "results", title: "Scenario results", icon: ListChecks },
  { id: "changes", title: "Changes", icon: FileCode2 },
  { id: "history", title: "History", icon: History },
] as const;

export function RefinementDashboard({
  view = "overview",
  tab = "results",
}: {
  view?: View;
  tab?: EvaluationTab;
}) {
  const {
    run,
    runs,
    selectedRun,
    selectRun,
    connection,
    receivedAt,
    iterationKey,
    selectIteration,
    scenarioId,
    selectScenario,
  } = useMonitoring();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(timer);
  }, []);
  const { iteration, scenario, selectedNumber } = resolveObservation(run, iterationKey, scenarioId);
  const threshold = run?.pass_score ?? 8;
  const live = run?.status === "running" && iteration?.number === run.iteration;
  const stale = run?.status === "running" && now - new Date(run.heartbeat_at).getTime() > 30_000;
  const chooseIteration = (number: number) => {
    selectIteration(`${run?.run_id}:${number}`);
    selectScenario("");
  };
  const scenarios = (iteration?.scenarios || []).filter(
    (item) =>
      `${scenarioName(item.id)} ${item.goal}`.toLowerCase().includes(query.toLowerCase()) &&
      (filter === "all" || needsAttention(item, threshold)),
  );
  const showInspector = () => {
    if (window.matchMedia("(max-width: 1023px)").matches)
      document.getElementById("conversation-inspector")?.scrollIntoView({ block: "start" });
  };
  const scores = <ScorePanel scenario={scenario} threshold={threshold} />;
  return (
    <>
      <div className="mb-8 flex flex-wrap items-start justify-between gap-5">
        <div>
          <h1 className="text-[28px] font-normal tracking-[-0.04em] sm:text-[34px]">
            {headings[view].title}
          </h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {headings[view].description}
          </p>
        </div>
        <div className="flex max-w-full flex-col gap-2 sm:items-end">
          <Select
            value={selectedRun || "__latest"}
            items={[
              { value: "__latest", label: "Latest run · automatic" },
              ...runs.map((item) => ({
                value: item.run_id,
                label: `${dateTime(item.started_at)} · ${item.run_id.slice(0, 8)}`,
              })),
            ]}
            onValueChange={(value) => {
              selectRun(value === "__latest" ? "" : value || "");
              selectIteration("");
              selectScenario("");
            }}
          >
            <SelectTrigger
              aria-label="Observed run"
              className="h-10 w-full max-w-[300px] bg-card text-[13px] sm:w-64"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__latest">Latest run · automatic</SelectItem>
              {runs.map((item) => (
                <SelectItem key={item.run_id} value={item.run_id}>
                  {dateTime(item.started_at)} · {item.run_id.slice(0, 8)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {receivedAt ? `Updated ${relative(receivedAt, now)}` : "Waiting for first snapshot"}
          </p>
        </div>
      </div>
      {connection === "reconnecting" && (
        <Alert role="status" className="mb-6 border-amber-200 bg-amber-50 text-amber-900">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>Reconnecting automatically</AlertTitle>
          <AlertDescription>
            {receivedAt
              ? "Showing the last received snapshot while the connection recovers."
              : "The monitoring service is unavailable. Retrying automatically."}
          </AlertDescription>
        </Alert>
      )}
      {stale && connection === "connected" && (
        <Alert role="status" className="mb-6 border-amber-200 bg-amber-50 text-amber-900">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>Worker heartbeat is stale</AlertTitle>
          <AlertDescription>
            The worker has stopped reporting. Showing its last recorded observations.
          </AlertDescription>
        </Alert>
      )}
      {run?.error && (
        <Alert variant="destructive" className="mb-6">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>Run stopped</AlertTitle>
          <AlertDescription>{run.error}</AlertDescription>
        </Alert>
      )}
      {!run ? (
        <WaitingForRun connected={connection === "connected"} view={view} />
      ) : view === "overview" ? (
        <RunOverview iteration={run.iterations.at(-1)} stale={stale} />
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-y py-3">
            <div className="flex flex-wrap items-center gap-3">
              <Label htmlFor="observed-iteration" className="text-xs text-muted-foreground">
                Iteration
              </Label>
              <Select
                value={
                  selectedNumber === null ? "__latest" : String(iteration?.number || "__latest")
                }
                items={[
                  { value: "__latest", label: `Latest · ${run.iteration}` },
                  ...run.iterations.map((item) => ({
                    value: String(item.number),
                    label: `Iteration ${item.number}`,
                  })),
                ]}
                onValueChange={(value) => {
                  if (value === "__latest") {
                    selectIteration("");
                    selectScenario("");
                  } else chooseIteration(Number(value));
                }}
              >
                <SelectTrigger
                  id="observed-iteration"
                  className="h-9 w-40 border-none bg-transparent text-[13px] shadow-none"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__latest">Latest · {run.iteration}</SelectItem>
                  {run.iterations.map((item) => (
                    <SelectItem key={item.number} value={String(item.number)}>
                      Iteration {item.number}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedNumber !== null && (
                <Button
                  variant="link"
                  className="h-9 px-0 text-xs"
                  onClick={() => {
                    selectIteration("");
                    selectScenario("");
                  }}
                >
                  Follow latest
                  <ArrowRight className="size-3" aria-hidden="true" />
                </Button>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              {iteration?.scenarios.length || 0} scenarios<span className="mx-2">·</span>Target{" "}
              {threshold}/10
            </span>
          </div>
          {view === "conversations" ? (
            <div className="grid items-start gap-6 lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)]">
              <aside
                aria-label="Scenario conversations"
                className="overflow-hidden rounded-lg border bg-card"
              >
                <div className="border-b p-4">
                  <h2 className="mb-4 flex items-center gap-2 text-sm font-medium">
                    <MessagesSquare className="size-4 text-muted-foreground" aria-hidden="true" />
                    Scenarios
                    <span className="ml-auto text-xs font-normal text-muted-foreground">
                      {iteration?.scenarios.length || 0}
                    </span>
                  </h2>
                  <div className="relative">
                    <Search
                      className="absolute top-3 left-3 size-3.5 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <Input
                      type="search"
                      aria-label="Search scenarios"
                      placeholder="Search scenarios…"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      className="h-10 pl-9 text-[13px]"
                    />
                  </div>
                  <div className="mt-3">
                    <Select
                      value={filter}
                      items={[
                        { value: "all", label: "All scenarios" },
                        { value: "issues", label: "Needs attention" },
                      ]}
                      onValueChange={(value) => setFilter(value || "all")}
                    >
                      <SelectTrigger aria-label="Filter scenarios" className="h-9 w-full text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All scenarios</SelectItem>
                        <SelectItem value="issues">Needs attention</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="max-h-64 overflow-y-auto p-2 lg:max-h-[540px]">
                  {scenarios.length ? (
                    scenarios.map((item) => (
                      <Button
                        key={item.id}
                        variant="ghost"
                        aria-pressed={scenario?.id === item.id}
                        onClick={() => {
                          selectScenario(item.id);
                          showInspector();
                        }}
                        className={`mb-1 h-auto w-full items-start justify-start whitespace-normal rounded-md border px-3 py-4 text-left ${scenario?.id === item.id ? "border-primary/20 bg-accent/60 hover:bg-accent" : "border-transparent"}`}
                      >
                        <span className="min-w-0">
                          <span className="block text-[13px] font-medium">
                            {scenarioName(item.id)}
                          </span>
                          <span className="mt-2 block">
                            <StatusBadge status={item.status} />
                          </span>
                          <span className="mt-2 block text-xs font-normal text-muted-foreground">
                            {item.dialogue.length} messages · {item.tools.length} tool calls
                          </span>
                        </span>
                      </Button>
                    ))
                  ) : (
                    <p className="px-3 py-8 text-[13px] leading-6 text-muted-foreground">
                      {query || filter !== "all"
                        ? "No scenarios match your filters."
                        : "Scenarios will appear as this iteration starts."}
                    </p>
                  )}
                </div>
              </aside>
              <div id="conversation-inspector" className="min-w-0 scroll-mt-6 space-y-6">
                {scenario && (
                  <div>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h2 className="text-xl font-normal tracking-tight">
                        {scenarioName(scenario.id)}
                      </h2>
                      <StatusBadge status={scenario.status} />
                    </div>
                    <p className="mt-2 max-w-3xl text-[13px] leading-6 text-muted-foreground">
                      {scenario.goal}
                    </p>
                  </div>
                )}
                <ConversationFeed
                  scenario={scenario}
                  live={
                    !!live &&
                    !stale &&
                    connection === "connected" &&
                    scenario?.status === "simulating"
                  }
                />
                {scenario?.evaluation && (
                  <div className="rounded-lg border bg-card p-5">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <h2 className="flex items-center gap-2 text-sm font-medium">
                        <CheckCheck className="size-4 text-primary" aria-hidden="true" />
                        Evaluation
                      </h2>
                      <Link
                        href="/evaluations"
                        className="flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        Inspect scores
                        <ArrowRight className="size-3" aria-hidden="true" />
                      </Link>
                    </div>
                    <p className="text-[13px] leading-6 text-muted-foreground">
                      {scenario.evaluation.rationale}
                    </p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <>
              <nav aria-label="Evaluation sections" className="mb-6 flex gap-3 border-b sm:gap-7">
                {tabs.map(({ id, title, icon: Icon }) => (
                  <Link
                    key={id}
                    href={id === "results" ? "/evaluations" : `/evaluations?tab=${id}`}
                    aria-current={tab === id ? "page" : undefined}
                    className={`relative flex shrink-0 items-center gap-2 border-b-2 px-0.5 pt-1 pb-4 text-[13px] ${tab === id ? "border-primary font-medium text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}
                  >
                    <Icon className="size-4" aria-hidden="true" />
                    {title}
                  </Link>
                ))}
              </nav>
              {tab === "results" && (
                <div className="space-y-6">
                  <ScenarioResults
                    iteration={iteration}
                    threshold={threshold}
                    selected={scenario?.id}
                    onSelect={selectScenario}
                  />
                  {scenario && (
                    <div
                      id="evaluation-detail"
                      className="grid scroll-mt-6 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
                    >
                      {scores}
                      <EvaluationDetails scenario={scenario} />
                    </div>
                  )}
                </div>
              )}
              {tab === "changes" && (
                <div className="max-w-5xl">
                  <ChangeDiff iteration={iteration} />
                </div>
              )}
              {tab === "history" && (
                <div className="max-w-4xl">
                  <IterationHistory
                    run={run}
                    selected={iteration?.number}
                    onSelect={chooseIteration}
                  />
                  <p className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                    <ArrowLeft className="size-3" aria-hidden="true" />
                    Select an iteration, then open its scenario results or changes.
                  </p>
                </div>
              )}
            </>
          )}
        </>
      )}
      <footer className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t pt-4 text-xs text-muted-foreground">
        <span>Airline assistant observability</span>
        <span>Read-only workspace</span>
      </footer>
    </>
  );
}
