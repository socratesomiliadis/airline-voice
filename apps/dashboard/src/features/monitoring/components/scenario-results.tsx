import { ArrowRight, Code2, ListChecks, MessageSquareText, Unplug } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { criteria, scenarioName } from "@/features/monitoring/format";
import type { IterationObservation, ScenarioObservation } from "@/lib/api/contracts";
import { ObservationEmpty, ObservationPanel } from "./observation-panel";
import { StatusBadge } from "./status-badge";

function Score({ value, threshold }: { value?: number; threshold: number }) {
  return (
    <span
      className={`inline-flex min-w-7 justify-center rounded px-1.5 py-1 font-mono text-[13px] tabular-nums ${value !== undefined && value < threshold ? "bg-amber-50 font-medium text-amber-800" : value === undefined ? "text-muted-foreground" : "text-foreground"}`}
    >
      {value ?? "—"}
    </span>
  );
}

export function ScenarioResults({
  iteration,
  threshold,
  selected,
  onSelect,
}: {
  iteration?: IterationObservation;
  threshold: number;
  selected?: string;
  onSelect: (id: string) => void;
}) {
  const choose = (id: string) => {
    onSelect(id);
    document.getElementById("evaluation-detail")?.scrollIntoView({ block: "nearest" });
  };
  return (
    <ObservationPanel
      title="Scenario results"
      subtitle="Select a scenario to inspect its scores and evidence"
      icon={ListChecks}
      action={
        <span className="text-xs text-muted-foreground">
          {iteration?.scenarios.filter((scenario) => scenario.evaluation).length || 0} evaluated
        </span>
      }
    >
      {!iteration?.scenarios.length ? (
        <ObservationEmpty
          title="No evaluations yet"
          description="Scores and failure diagnoses will appear after the first conversation is evaluated."
        />
      ) : (
        <>
          <div className="hidden sm:block">
            <Table className="text-[13px]">
              <TableCaption className="sr-only">
                Scenario evaluation scores for iteration {iteration.number}; each criterion must
                score at least {threshold}. Select a scenario to see its details below.
              </TableCaption>
              <TableHeader>
                <TableRow className="bg-background/70 hover:bg-background/70">
                  <TableHead className="px-5 py-3">Scenario</TableHead>
                  {criteria.map(({ key, short }) => (
                    <TableHead
                      key={key}
                      className="px-2 py-3 text-center text-xs font-normal whitespace-normal"
                    >
                      {short}
                    </TableHead>
                  ))}
                  <TableHead className="px-5 text-right">Result</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {iteration.scenarios.map((scenario) => (
                  <TableRow
                    key={scenario.id}
                    data-state={selected === scenario.id ? "selected" : undefined}
                    className="data-[state=selected]:bg-accent/50"
                  >
                    <TableHead scope="row" className="px-5 py-3">
                      <Button
                        variant="link"
                        aria-pressed={selected === scenario.id}
                        onClick={() => choose(scenario.id)}
                        className="h-auto min-h-10 justify-start whitespace-normal p-0 text-left text-[13px] font-medium text-foreground"
                      >
                        {scenarioName(scenario.id)}
                      </Button>
                    </TableHead>
                    {criteria.map(({ key }) => (
                      <TableCell key={key} className="px-2 py-3 text-center">
                        <Score value={scenario.evaluation?.scores[key]} threshold={threshold} />
                      </TableCell>
                    ))}
                    <TableCell className="px-5 py-3 text-right">
                      <StatusBadge status={scenario.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="divide-y sm:hidden">
            {iteration.scenarios.map((scenario) => (
              <Button
                key={scenario.id}
                variant="ghost"
                aria-pressed={selected === scenario.id}
                onClick={() => choose(scenario.id)}
                className={`h-auto w-full flex-col items-stretch gap-4 rounded-none px-5 py-4 whitespace-normal ${selected === scenario.id ? "bg-accent/50" : ""}`}
              >
                <span className="flex flex-wrap items-center justify-between gap-2 text-left text-[13px]">
                  <span>{scenarioName(scenario.id)}</span>
                  <StatusBadge status={scenario.status} />
                </span>
                <span className="grid grid-cols-2 gap-x-4 gap-y-2">
                  {criteria.map(({ key, short }) => (
                    <span
                      key={key}
                      className="flex items-center justify-between text-xs font-normal text-muted-foreground"
                    >
                      <span>{short}</span>
                      <Score value={scenario.evaluation?.scores[key]} threshold={threshold} />
                    </span>
                  ))}
                </span>
              </Button>
            ))}
          </div>
        </>
      )}
    </ObservationPanel>
  );
}

export function EvaluationDetails({ scenario }: { scenario: ScenarioObservation }) {
  return (
    <section
      aria-label="Selected scenario evidence"
      className="min-w-0 rounded-lg border bg-card p-5"
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">Evaluation evidence</p>
          <h2 className="text-[15px] font-medium">{scenarioName(scenario.id)}</h2>
        </div>
        <Link
          href="/conversations"
          className="flex items-center gap-1 text-xs text-primary hover:underline"
        >
          Read conversation
          <ArrowRight className="size-3" aria-hidden="true" />
        </Link>
      </div>
      <p className="text-[13px] leading-6 text-muted-foreground">
        {scenario.evaluation?.rationale || scenario.goal}
      </p>
      {!scenario.evaluation && (
        <p className="mt-4 text-xs text-muted-foreground">Evaluation pending</p>
      )}
      {scenario.errors.map((error) => (
        <p
          key={error}
          className="mt-4 rounded-md bg-amber-50 p-3 text-[13px] leading-6 text-amber-900"
        >
          {error}
        </p>
      ))}
      {scenario.evaluation?.failures.map((failure) => (
        <div
          key={`${failure.criterion}:${failure.root_cause}:${failure.quote}:${failure.explanation}`}
          className="mt-5 border-t pt-5"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-1.5 text-xs">
              {failure.root_cause === "code" ? (
                <Code2 aria-hidden="true" />
              ) : failure.root_cause === "infrastructure" ? (
                <Unplug aria-hidden="true" />
              ) : (
                <MessageSquareText aria-hidden="true" />
              )}
              {failure.root_cause === "code"
                ? "Code issue"
                : failure.root_cause === "infrastructure"
                  ? "Infrastructure issue"
                  : "Prompt issue"}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {criteria.find(({ key }) => key === failure.criterion)?.short}
            </span>
          </div>
          <blockquote className="mt-4 border-l-2 border-amber-400 pl-3 text-[13px] leading-6">
            “{failure.quote}”
          </blockquote>
          <p className="mt-3 text-[13px] leading-6 text-muted-foreground">{failure.explanation}</p>
          {failure.code_faults.map((fault) => (
            <div key={`${fault.path}:${fault.function}`} className="mt-3">
              <p className="break-all font-mono text-xs leading-6">
                {fault.path} · {fault.function}
              </p>
              <p className="mt-1 text-[13px] leading-6 text-muted-foreground">{fault.behavior}</p>
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}
