"use client";

import { ChartNoAxesCombined, Target } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { criteria, minimumScores, scenarioName } from "@/features/monitoring/format";
import type { IterationObservation, ScenarioObservation } from "@/lib/api/contracts";
import { ObservationEmpty, ObservationPanel } from "./observation-panel";

/** Four small series do not need a chart runtime. Keep coordinates at CSS-pixel size. */
export function ScoreTrend({
  iterations,
  threshold,
  limit,
}: {
  iterations: IterationObservation[];
  threshold: number;
  limit: number;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.max(200, Math.floor(entry.contentRect.width))),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const points = iterations.flatMap((iteration) => {
    const scores = minimumScores(iteration);
    return scores ? [{ number: iteration.number, ...scores }] : [];
  });
  const last = Math.max(2, limit, ...points.map((point) => point.number));
  const x = (number: number) => 28 + ((number - 1) / (last - 1)) * (width - 48);
  const y = (score: number) => 198 - score * 17;
  const ticks = Array.from(
    new Set(
      Array.from({ length: Math.min(last, 6) }, (_, index) =>
        Math.round(1 + (index * (last - 1)) / (Math.min(last, 6) - 1)),
      ),
    ),
  );
  return (
    <div className="px-5 py-5" ref={container}>
      {points.length ? (
        <>
          <svg
            viewBox={`0 0 ${width} 232`}
            width="100%"
            height="232"
            role="img"
            aria-label={`Minimum quality scores by iteration. Target ${threshold} out of 10.`}
            className="overflow-visible"
          >
            <title>Quality over time</title>
            <desc>
              {points
                .map(
                  (point) =>
                    `Iteration ${point.number}: ${criteria.map(({ key, short }) => `${short} ${point[key]}`).join(", ")}.`,
                )
                .join(" ")}
            </desc>
            {[0, 2, 4, 6, 8, 10].map((score) => (
              <g key={score}>
                <line
                  x1="28"
                  x2={width - 20}
                  y1={y(score)}
                  y2={y(score)}
                  stroke="var(--border)"
                  strokeDasharray="2 4"
                />
                <text
                  x="18"
                  y={y(score) + 4}
                  textAnchor="end"
                  fill="var(--muted-foreground)"
                  fontSize="12"
                >
                  {score}
                </text>
              </g>
            ))}
            {ticks.map((number) => (
              <text
                key={number}
                x={x(number)}
                y="224"
                textAnchor="middle"
                fill="var(--muted-foreground)"
                fontSize="12"
              >
                {number}
              </text>
            ))}
            <line
              x1="28"
              x2={width - 20}
              y1={y(threshold)}
              y2={y(threshold)}
              stroke="var(--primary)"
              strokeDasharray="4 4"
            />
            <text
              x={width - 20}
              y={y(threshold) - 8}
              textAnchor="end"
              fill="var(--primary)"
              fontSize="12"
            >
              Target {threshold}
            </text>
            {criteria.map(({ key, color, short }) => (
              <g key={key}>
                <polyline
                  points={points.map((point) => `${x(point.number)},${y(point[key])}`).join(" ")}
                  fill="none"
                  stroke={color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                />
                {points.map((point) => (
                  <circle
                    key={point.number}
                    cx={x(point.number)}
                    cy={y(point[key])}
                    r="3.5"
                    fill="var(--card)"
                    stroke={color}
                    strokeWidth="2"
                  >
                    <title>{`Iteration ${point.number} · ${short}: ${point[key]} / 10`}</title>
                  </circle>
                ))}
              </g>
            ))}
          </svg>
          <ul
            aria-label="Score criteria"
            className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs text-muted-foreground sm:flex sm:flex-wrap sm:justify-center sm:gap-x-4"
          >
            {criteria.map(({ key, short, color }) => (
              <li key={key} className="flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="size-2 shrink-0 rounded-sm"
                  style={{ backgroundColor: color }}
                />
                {short}
              </li>
            ))}
          </ul>
        </>
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
  threshold,
}: {
  scenario?: ScenarioObservation;
  threshold: number;
}) {
  return (
    <ObservationPanel
      title="Selected scenario scores"
      subtitle={scenario ? scenarioName(scenario.id) : "Each criterion must meet the target"}
      icon={ChartNoAxesCombined}
      action={
        <Badge variant="outline" className="text-xs">
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
                  className={`font-mono text-xs ${score !== undefined && score < threshold ? "bg-amber-50 text-amber-800" : ""}`}
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
    </ObservationPanel>
  );
}
