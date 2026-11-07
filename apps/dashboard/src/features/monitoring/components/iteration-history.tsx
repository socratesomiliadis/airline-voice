import { Check, ChevronRight, Circle, History, LoaderCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { label, minimumScores, passedCount, time } from "@/features/monitoring/format";
import type { RunObservation } from "@/lib/api/contracts";
import { ObservationEmpty, ObservationPanel } from "./observation-panel";

export function IterationHistory({
  run,
  selected,
  onSelect,
}: {
  run: RunObservation | null;
  selected?: number;
  onSelect: (number: number) => void;
}) {
  return (
    <ObservationPanel
      title="Iteration history"
      subtitle="Every evaluation and refinement cycle"
      icon={History}
      action={
        <Badge variant="outline" className="font-mono text-[10px]">
          {run ? `${run.iteration} / ${run.max_iterations}` : "Awaiting run"}
        </Badge>
      }
    >
      {!run?.iterations.length ? (
        <ObservationEmpty
          title="The first iteration is ahead"
          description="A history of conversations, scores and improvements builds automatically as the loop runs."
        />
      ) : (
        <ScrollArea className="max-h-[480px] [&_[data-slot=scroll-area-viewport]]:max-h-[480px]">
          <div className="space-y-2 p-3">
            {[...run.iterations].reverse().map((iteration) => {
              const scores = minimumScores(iteration);
              const passing = passedCount(iteration, run.pass_score);
              const completed = iteration.scenarios.every((scenario) => scenario.evaluation);
              const passed = completed && passing === iteration.scenarios.length;
              const active = iteration.number === run.iteration && run.status === "running";
              const Icon = passed ? Check : active ? LoaderCircle : Circle;
              return (
                <Button
                  key={iteration.number}
                  variant={selected === iteration.number ? "outline" : "ghost"}
                  aria-pressed={selected === iteration.number}
                  onClick={() => onSelect(iteration.number)}
                  className={`h-auto w-full items-start justify-start gap-3 whitespace-normal px-3 py-4 text-left ${selected === iteration.number ? "border-primary/30 bg-accent/60" : ""}`}
                >
                  <Icon
                    className={`mt-0.5 size-4 ${passed ? "text-primary" : active ? "text-primary motion-safe:animate-spin" : "text-muted-foreground"}`}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold">Iteration {iteration.number}</span>
                      <time
                        className="font-mono text-[9px] text-muted-foreground"
                        dateTime={iteration.started_at}
                      >
                        {time(iteration.started_at)}
                      </time>
                    </span>
                    <span className="mt-1.5 block text-[11px] text-muted-foreground">
                      {active
                        ? label(iteration.stage)
                        : passed
                          ? "All scenarios passed"
                          : completed
                            ? `${passing} of ${iteration.scenarios.length} scenarios passed`
                            : "Incomplete iteration"}
                    </span>
                    <span className="mt-3 flex flex-wrap gap-2">
                      <Badge
                        variant={
                          scores && Math.min(...Object.values(scores)) >= run.pass_score
                            ? "default"
                            : "outline"
                        }
                        className="text-[9px]"
                      >
                        {scores
                          ? `Lowest ${Math.min(...Object.values(scores))}/10`
                          : "Scores pending"}
                      </Badge>
                      {iteration.change_status !== "none" && (
                        <Badge variant="outline" className="text-[9px]">
                          {label(iteration.change_status)}
                        </Badge>
                      )}
                    </span>
                  </span>
                  <ChevronRight className="mt-1 size-3 text-muted-foreground" aria-hidden="true" />
                </Button>
              );
            })}
          </div>
        </ScrollArea>
      )}
    </ObservationPanel>
  );
}
