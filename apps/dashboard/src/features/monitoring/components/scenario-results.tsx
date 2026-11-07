import { Check, Code2, ListChecks, MessageSquareText } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { criteria, label, scenarioName } from "@/features/monitoring/format";
import type { IterationObservation } from "@/lib/api/contracts";
import { ObservationEmpty, ObservationPanel } from "./observation-panel";

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
  return (
    <ObservationPanel
      title="Scenario results"
      subtitle="Independent evaluation across all four criteria"
      icon={ListChecks}
      action={
        <Badge variant="outline" className="text-[10px]">
          {iteration?.scenarios.filter((scenario) => scenario.evaluation).length || 0} evaluated
        </Badge>
      }
    >
      {!iteration ? (
        <ObservationEmpty
          title="No evaluations yet"
          description="Scores and evidence-backed failure diagnoses will appear after each conversation."
        />
      ) : (
        <>
          <Table className="min-w-[640px] text-xs">
            <TableCaption className="sr-only">
              Scenario evaluation scores for iteration {iteration.number}; each criterion must score
              at least {threshold}.
            </TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead className="px-5">Scenario</TableHead>
                {criteria.map(({ key, short }) => (
                  <TableHead key={key} className="px-3 text-center text-[10px]">
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
                >
                  <TableHead scope="row" className="px-5">
                    <Button
                      variant="link"
                      size="xs"
                      onClick={() => onSelect(scenario.id)}
                      className="justify-start p-0 text-left"
                    >
                      {scenarioName(scenario.id)}
                    </Button>
                  </TableHead>
                  {criteria.map(({ key }) => {
                    const score = scenario.evaluation?.scores[key];
                    return (
                      <TableCell key={key} className="px-3 text-center">
                        <Badge
                          variant={
                            score === undefined
                              ? "outline"
                              : score >= threshold
                                ? "default"
                                : "secondary"
                          }
                          className="font-mono text-[10px]"
                        >
                          {score === undefined ? "Pending" : score}
                        </Badge>
                      </TableCell>
                    );
                  })}
                  <TableCell className="px-5 text-right">
                    <Badge
                      variant={
                        scenario.status === "passed"
                          ? "default"
                          : scenario.status === "error"
                            ? "destructive"
                            : scenario.status === "failed"
                              ? "secondary"
                              : "outline"
                      }
                      className="text-[10px]"
                    >
                      {scenario.status === "passed" && <Check aria-hidden="true" />}
                      {label(scenario.status)}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Accordion multiple className="border-t px-5">
            {iteration.scenarios
              .filter((scenario) => scenario.evaluation)
              .map((scenario) => (
                <AccordionItem key={scenario.id} value={scenario.id}>
                  <AccordionTrigger className="text-[11px]">
                    <span className="flex flex-wrap items-center gap-2">
                      <span>{scenarioName(scenario.id)}</span>
                      <span className="text-muted-foreground">
                        {scenario.evaluation?.failures.length
                          ? `${scenario.evaluation.failures.length} diagnosed failures`
                          : "Evaluation rationale"}
                      </span>
                    </span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <p className="text-xs leading-6 text-muted-foreground">
                      {scenario.evaluation?.rationale}
                    </p>
                    {scenario.evaluation?.failures.map((failure) => (
                      <Card
                        key={`${failure.criterion}:${failure.root_cause}:${failure.quote}:${failure.explanation}`}
                        size="sm"
                        className="mt-3"
                      >
                        <CardContent>
                          <Badge variant={failure.root_cause === "code" ? "secondary" : "outline"}>
                            {failure.root_cause === "code" ? (
                              <Code2 aria-hidden="true" />
                            ) : (
                              <MessageSquareText aria-hidden="true" />
                            )}
                            {failure.root_cause === "code" ? "Code issue" : "Prompt issue"}
                          </Badge>
                          <blockquote className="mt-3 border-l-2 border-primary/30 pl-3 text-xs leading-6">
                            “{failure.quote}”
                          </blockquote>
                          <p className="mt-2 text-xs leading-6 text-muted-foreground">
                            {failure.explanation}
                          </p>
                          {failure.code_faults.map((fault) => (
                            <p
                              key={`${fault.path}:${fault.function}`}
                              className="mt-2 break-words font-mono text-[10px] leading-5 text-muted-foreground"
                            >
                              {fault.path} · {fault.function}
                              <span className="block font-sans text-xs">{fault.behavior}</span>
                            </p>
                          ))}
                        </CardContent>
                      </Card>
                    ))}
                  </AccordionContent>
                </AccordionItem>
              ))}
          </Accordion>
        </>
      )}
    </ObservationPanel>
  );
}
