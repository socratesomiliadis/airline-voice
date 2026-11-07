import {
  ArrowRight,
  Check,
  CircleAlert,
  GitBranch,
  MessagesSquare,
  ScanLine,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  criteria,
  dateTime,
  label,
  minimumScores,
  passedCount,
  scenarioName,
} from "@/features/monitoring/format";
import { useMonitoring } from "@/features/monitoring/monitoring-provider";
import { needsAttention } from "@/features/monitoring/selection";
import type { IterationObservation } from "@/lib/api/contracts";
import { ObservationEmpty, ObservationPanel } from "./observation-panel";
import { ScoreTrend } from "./score-panel";
import { StatusBadge } from "./status-badge";

const stages = [
  {
    title: "Simulate",
    description: "Customer conversations",
    icon: MessagesSquare,
    stages: ["preparing", "simulating"],
  },
  {
    title: "Evaluate",
    description: "Four quality criteria",
    icon: ShieldCheck,
    stages: ["evaluating"],
  },
  {
    title: "Refine",
    description: "Targeted improvements",
    icon: Sparkles,
    stages: ["repairing", "verifying", "reloading", "publishing", "rollback"],
  },
];

export function Pipeline({ stage, complete = false }: { stage?: string; complete?: boolean }) {
  const active = stages.findIndex((item) => item.stages.includes(stage || ""));
  return (
    <ol aria-label="Refinement stages" className="grid grid-cols-3 gap-3 sm:gap-6">
      {stages.map(({ title, description, icon: Icon }, index) => {
        const done = complete || (active >= 0 && index < active);
        const current = active === index && !complete;
        return (
          <li
            key={title}
            aria-current={current ? "step" : undefined}
            className={`flex flex-col items-start gap-2 border-t-2 pt-4 sm:flex-row sm:items-center sm:gap-3 ${done || current ? "border-primary/70" : "border-border"}`}
          >
            <span
              className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${current ? "bg-primary text-primary-foreground" : done ? "bg-accent text-primary" : "bg-muted text-muted-foreground"}`}
            >
              {done ? (
                <Check className="size-4" aria-hidden="true" />
              ) : (
                <Icon className="size-4" aria-hidden="true" />
              )}
            </span>
            <div>
              <p className="text-sm font-medium">{title}</p>
              <p className="mt-0.5 hidden text-xs text-muted-foreground sm:block">{description}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function WaitingForRun({
  connected,
  view = "overview",
}: {
  connected: boolean;
  view?: "overview" | "conversations" | "evaluations";
}) {
  const Icon =
    view === "conversations" ? MessagesSquare : view === "evaluations" ? ShieldCheck : ScanLine;
  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <div className="px-6 py-10 sm:px-10 sm:py-12">
        <span className="mb-6 flex size-12 items-center justify-center rounded-xl border bg-background text-primary">
          <Icon className="size-6" aria-hidden="true" />
        </span>
        <p className="mb-3 text-[13px] font-medium text-primary">
          {connected ? "Ready to observe" : "Establishing connection"}
        </p>
        <h2 className="max-w-lg text-2xl font-normal tracking-tight sm:text-3xl">
          {view === "conversations"
            ? "No conversations to inspect yet."
            : view === "evaluations"
              ? "No evaluations recorded yet."
              : "Your next run starts here."}
        </h2>
        <p className="mt-4 max-w-lg text-sm leading-7 text-muted-foreground">
          {connected
            ? view === "conversations"
              ? "When the worker simulates a scenario, its transcript and tool calls will appear here. Select a conversation to follow each decision."
              : view === "evaluations"
                ? "Quality scores appear after each scenario is evaluated. Inspect failures, compare iterations, and review the prompt and code changes in one place."
                : "No refinement runs have been recorded yet. When the worker starts, follow its conversations, quality scores, and improvements here in real time."
            : "Connecting to the monitoring service. Recorded runs will appear as soon as a snapshot arrives."}
        </p>
        {view === "overview" && (
          <div className="mt-10 max-w-3xl">
            <Pipeline />
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 border-t bg-muted/30 px-6 py-4 text-xs text-muted-foreground sm:px-10">
        <ScanLine className="size-3.5 shrink-0" aria-hidden="true" />
        Updates arrive automatically. No refresh needed.
      </div>
    </div>
  );
}

export function RunOverview({
  iteration,
  stale,
}: {
  iteration?: IterationObservation;
  stale: boolean;
}) {
  const { run, runs, selectRun, selectIteration, selectScenario } = useMonitoring();
  if (!run) return null;
  const threshold = run.pass_score;
  const scores = iteration ? minimumScores(iteration) : null;
  const passing = passedCount(iteration, threshold);
  const evaluated = iteration?.scenarios.filter((item) => item.evaluation).length || 0;
  const count = iteration?.scenarios.length || run.scenario_count;
  const issues = iteration?.scenarios.filter((item) => needsAttention(item, threshold)) || [];
  return (
    <div className="space-y-6">
      <section aria-label="Current run" className="overflow-hidden rounded-lg border bg-card">
        <div className="px-6 pt-6 sm:px-7 sm:pt-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
              <span
                className={`size-2 rounded-full ${run.status === "running" && !stale ? "bg-primary" : "bg-muted-foreground"}`}
              />
              {run.status === "running" ? "Run in progress" : "Run summary"}
              <span aria-hidden="true" className="mx-1 text-muted-foreground">
                /
              </span>
              <span className="font-mono text-xs">{run.run_id.slice(0, 8)}</span>
            </div>
            <StatusBadge status={stale && run.status === "running" ? "stale" : run.status} />
          </div>
          <h2 className="mt-5 text-2xl font-normal tracking-tight sm:text-[28px]">
            {stale
              ? "Waiting for the worker"
              : label(run.status === "running" ? run.stage : run.status)}
          </h2>
          <p className="mt-2 text-[13px] leading-6 text-muted-foreground">
            Started {dateTime(run.started_at)}
            <span className="mx-2">·</span>Iteration {run.iteration} of {run.max_iterations}
          </p>
          <div className="mt-7 pb-7">
            <Pipeline
              stage={run.status === "running" && !stale ? run.stage : undefined}
              complete={run.status === "passed"}
            />
          </div>
        </div>
        <dl className="grid grid-cols-2 border-t bg-background/50 lg:grid-cols-4">
          {[
            {
              title: "Scenarios passing",
              value: `${passing}`,
              suffix: `/ ${count}`,
              detail: `${evaluated} evaluated`,
            },
            {
              title: "Lowest score",
              value: scores ? `${Math.min(...Object.values(scores))}` : "—",
              suffix: scores ? "/ 10" : "",
              detail: "Across evaluated scenarios",
            },
            {
              title: "Quality target",
              value: `${threshold}`,
              suffix: "/ 10",
              detail: "Required in every criterion",
            },
            {
              title: "Recorded changes",
              value: `${run.iterations.filter((item) => item.prompt_diff || item.code_diff).length}`,
              suffix: "",
              detail: "Iterations with a repair",
            },
          ].map(({ title, value, suffix, detail }) => (
            <div
              key={title}
              className="border-border px-5 py-5 even:border-l sm:px-6 [&:nth-child(n+3)]:border-t lg:[&:not(:first-child)]:border-l lg:[&:nth-child(n+3)]:border-t-0"
            >
              <dt className="text-xs text-muted-foreground">{title}</dt>
              <dd className="mt-2 text-[28px] font-normal tracking-tight tabular-nums">
                {value}
                <span className="ml-1.5 text-sm text-muted-foreground">{suffix}</span>
              </dd>
              <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
            </div>
          ))}
        </dl>
      </section>
      <div className="grid items-stretch gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <ObservationPanel
          title="Quality over time"
          subtitle="Lowest score for each criterion"
          icon={GitBranch}
          action={<span className="text-xs text-muted-foreground">Target {threshold}/10</span>}
        >
          <ScoreTrend
            iterations={run.iterations}
            threshold={threshold}
            limit={run.max_iterations}
          />
        </ObservationPanel>
        <ObservationPanel
          title="Needs attention"
          subtitle={
            issues.length
              ? `${issues.length} ${issues.length === 1 ? "scenario needs" : "scenarios need"} improvement`
              : "Failures and errors in this iteration"
          }
          icon={CircleAlert}
          action={
            <Link
              href="/evaluations"
              className="flex items-center gap-1 text-xs text-primary hover:underline"
            >
              View results
              <ArrowRight className="size-3" aria-hidden="true" />
            </Link>
          }
        >
          {issues.length ? (
            <ul className="divide-y">
              {issues.map((scenario) => (
                <li key={scenario.id}>
                  <Link
                    href="/evaluations"
                    onClick={() => {
                      selectIteration("");
                      selectScenario(scenario.id);
                    }}
                    className="group flex items-start gap-3 px-5 py-4 hover:bg-muted/50"
                  >
                    <span className="mt-1 size-1.5 shrink-0 rounded-full bg-amber-600" />
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium">{scenarioName(scenario.id)}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        {scenario.errors[0] ||
                          `${criteria
                            .filter(
                              ({ key }) => (scenario.evaluation?.scores[key] ?? 10) < threshold,
                            )
                            .map(({ short }) => short)
                            .join(", ")} below target`}
                      </p>
                    </div>
                    <ArrowRight
                      className="mt-1 size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-1"
                      aria-hidden="true"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <ObservationEmpty
              title={evaluated ? "No issues in evaluated scenarios" : "Evaluation is still ahead"}
              description={
                evaluated
                  ? "All scores received so far meet the quality target. Any new failures will appear here."
                  : "Scenarios that fall below the quality target will be collected here."
              }
            />
          )}
        </ObservationPanel>
      </div>
      <ObservationPanel
        title="Recent runs"
        subtitle="Select a run to inspect its observations"
        icon={ScanLine}
        action={<span className="text-xs text-muted-foreground">{runs.length} recorded</span>}
      >
        <div className="divide-y">
          {runs.slice(0, 5).map((item) => (
            <Button
              key={item.run_id}
              variant="ghost"
              onClick={() => {
                selectRun(item.run_id);
                selectIteration("");
                selectScenario("");
              }}
              className="h-auto w-full flex-wrap justify-between gap-3 rounded-none px-5 py-4 text-left"
            >
              <span className="flex min-w-0 items-center gap-4">
                <span className="hidden size-8 items-center justify-center rounded-md border bg-background sm:flex">
                  <ScanLine className="size-4 text-muted-foreground" aria-hidden="true" />
                </span>
                <span>
                  <span className="block font-mono text-xs">{item.run_id.slice(0, 12)}</span>
                  <span className="mt-1 block text-xs font-normal text-muted-foreground">
                    {dateTime(item.started_at)}
                  </span>
                </span>
              </span>
              <span className="flex items-center gap-4">
                <span className="hidden text-xs font-normal text-muted-foreground sm:inline">
                  {item.iteration} iterations
                </span>
                <StatusBadge status={item.status} />
                <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden="true" />
              </span>
            </Button>
          ))}
        </div>
      </ObservationPanel>
    </div>
  );
}
