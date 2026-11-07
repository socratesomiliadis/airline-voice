import type { Criterion, IterationObservation, Scores } from "@/lib/api/contracts";

export const criteria: { key: Criterion; label: string; short: string; color: string }[] = [
  { key: "understanding", label: "Request understood", short: "Understanding", color: "#059669" },
  {
    key: "api_correctness",
    label: "Correct API & parameters",
    short: "API correctness",
    color: "#6366f1",
  },
  {
    key: "outcome_confirmation",
    label: "Outcome confirmed",
    short: "Confirmation",
    color: "#0ea5e9",
  },
  { key: "naturalness", label: "Natural conversation", short: "Naturalness", color: "#f59e0b" },
];
export const stageLabels: Record<string, string> = {
  preparing: "Preparing scenarios",
  simulating: "Simulating conversation",
  evaluating: "Evaluating results",
  repairing: "Generating improvements",
  verifying: "Verifying code changes",
  reloading: "Reloading service",
  publishing: "Publishing prompt",
  rollback: "Restoring previous version",
  completed: "Run complete",
  error: "Run stopped",
  pending: "Queued",
  passed: "Passed",
  failed: "Below target",
  running: "Running",
  iteration_limit: "Iteration limit reached",
  proposed: "Proposed",
  applied: "Applied",
  rolled_back: "Rolled back",
  recovery_failed: "Recovery failed",
  none: "No changes",
};
export function label(value: string) {
  return stageLabels[value] || value.replaceAll("_", " ");
}
export function scenarioName(value: string) {
  return value
    .split("-")
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}
export function time(value: string) {
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
export function dateTime(value: string) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
export function relative(value: string | number, now: number) {
  const seconds = Math.max(0, Math.floor((now - new Date(value).getTime()) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}
export function minimumScores(iteration: IterationObservation): Scores | null {
  const evaluations = iteration.scenarios.flatMap((scenario) =>
    scenario.evaluation ? [scenario.evaluation] : [],
  );
  if (!evaluations.length) return null;
  return Object.fromEntries(
    criteria.map(({ key }) => [key, Math.min(...evaluations.map((item) => item.scores[key]))]),
  ) as Scores;
}
export function passedCount(iteration: IterationObservation | undefined, threshold: number) {
  return (
    iteration?.scenarios.filter(
      (scenario) =>
        scenario.evaluation &&
        Object.values(scenario.evaluation.scores).every((score) => score >= threshold),
    ).length || 0
  );
}

export function diffLines(diff: string) {
  let oldLine = 0;
  let newLine = 0;
  return diff
    .split("\n")
    .filter((line, index, lines) => index < lines.length - 1 || line.length > 0)
    .map((text, index) => {
      const hunk = text.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      let kind: "added" | "removed" | "context" | "header" = "context";
      let before: number | null = null;
      let after: number | null = null;
      if (hunk) {
        oldLine = Number(hunk[1]);
        newLine = Number(hunk[2]);
        kind = "header";
      } else if (
        text.startsWith("+++") ||
        text.startsWith("---") ||
        text.startsWith("diff ") ||
        text.startsWith("index ")
      )
        kind = "header";
      else if (text.startsWith("+")) {
        kind = "added";
        after = newLine++;
      } else if (text.startsWith("-")) {
        kind = "removed";
        before = oldLine++;
      } else if (!text.startsWith("\\")) {
        before = oldLine++;
        after = newLine++;
      }
      return {
        id: `${index}:${text}`,
        text: kind === "header" ? text : text.slice(1),
        kind,
        before,
        after,
      };
    });
}
