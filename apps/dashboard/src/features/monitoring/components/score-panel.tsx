"use client";

import { ChartNoAxesCombined, Target } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { Progress } from "@/components/ui/progress";
import { criteria, minimumScores } from "@/features/monitoring/format";
import type { IterationObservation, ScenarioObservation } from "@/lib/api/contracts";
import { ObservationEmpty, ObservationPanel } from "./observation-panel";

const chartConfig = Object.fromEntries(
  criteria.map(({ key, short, color }) => [key, { label: short, color }]),
) satisfies ChartConfig;

export function ScoreTrend({
  iterations,
  threshold,
  limit,
}: {
  iterations: IterationObservation[];
  threshold: number;
  limit: number;
}) {
  const points = iterations.flatMap((iteration) => {
    const scores = minimumScores(iteration);
    return scores ? [{ number: iteration.number, ...scores }] : [];
  });
  return (
    <div className="border-t px-5 pt-4 pb-3">
      <p className="mb-3 text-[10px] font-medium text-muted-foreground">
        Lowest score per criterion, by iteration
      </p>
      {points.length ? (
        <ChartContainer
          config={chartConfig}
          className="h-[210px] w-full"
          aria-label={`Quality scores across iterations. Target ${threshold} out of 10.`}
        >
          <LineChart
            accessibilityLayer
            data={points}
            margin={{ top: 15, right: 15, bottom: 5, left: -25 }}
          >
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="number"
              type="number"
              domain={[1, Math.max(2, limit)]}
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              tickMargin={8}
            />
            <YAxis domain={[0, 10]} ticks={[2, 4, 6, 8, 10]} tickLine={false} axisLine={false} />
            <ReferenceLine
              y={threshold}
              stroke="var(--primary)"
              strokeDasharray="4 4"
              label={{
                value: `Target ${threshold}`,
                position: "insideTopRight",
                fontSize: 10,
                fill: "var(--primary)",
              }}
            />
            <ChartTooltip
              content={<ChartTooltipContent labelFormatter={(value) => `Iteration ${value}`} />}
            />
            <ChartLegend content={<ChartLegendContent className="flex-wrap text-[10px]" />} />
            {criteria.map(({ key }) => (
              <Line
                key={key}
                dataKey={key}
                type="linear"
                stroke={`var(--color-${key})`}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 4 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ChartContainer>
      ) : (
        <ObservationEmpty
          title="Awaiting evaluation results"
          description="Iteration trends appear when the first independent scores arrive."
        />
      )}
    </div>
  );
}
export function ScorePanel({
  scenario,
  iterations,
  threshold,
  limit,
}: {
  scenario?: ScenarioObservation;
  iterations: IterationObservation[];
  threshold: number;
  limit: number;
}) {
  return (
    <ObservationPanel
      title="Evaluation scores"
      subtitle="Each criterion must meet the target"
      icon={ChartNoAxesCombined}
      action={
        <Badge variant="outline" className="text-[10px]">
          <Target aria-hidden="true" />
          {threshold}/10 to pass
        </Badge>
      }
    >
      <div className="space-y-4 px-5 py-5">
        {criteria.map(({ key, label }) => {
          const score = scenario?.evaluation?.scores[key];
          return (
            <div key={key}>
              <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                <span className="text-muted-foreground">{label}</span>
                <Badge
                  variant={
                    score === undefined ? "outline" : score >= threshold ? "default" : "secondary"
                  }
                  className="font-mono text-[10px]"
                >
                  {score === undefined ? "Pending" : `${score} / 10`}
                </Badge>
              </div>
              <div className="relative">
                <Progress
                  aria-label={label}
                  aria-valuetext={
                    score === undefined
                      ? "Not yet evaluated"
                      : `${score} out of 10; target ${threshold}`
                  }
                  value={score ?? null}
                  max={10}
                  className={
                    score !== undefined && score < threshold
                      ? "[&_[data-slot=progress-indicator]]:bg-amber-400"
                      : ""
                  }
                />
                <span
                  aria-hidden="true"
                  className="absolute -top-0.5 h-2 w-px bg-muted-foreground/50"
                  style={{ left: `${threshold * 10}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <ScoreTrend iterations={iterations} threshold={threshold} limit={limit} />
    </ObservationPanel>
  );
}
