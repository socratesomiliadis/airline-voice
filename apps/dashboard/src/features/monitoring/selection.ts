import type { RunObservation, ScenarioObservation } from "@/lib/api/contracts";

/** Ignore an iteration pinned in another run, and follow live data unless explicitly selected. */
export function resolveObservation(
  run: RunObservation | null,
  iterationKey: string,
  scenarioId: string,
) {
  const selectedNumber =
    run && iterationKey.startsWith(`${run.run_id}:`)
      ? Number(iterationKey.slice(run.run_id.length + 1))
      : null;
  const iteration =
    run?.iterations.find((item) => item.number === selectedNumber) || run?.iterations.at(-1);
  const scenario =
    iteration?.scenarios.find((item) => item.id === scenarioId) ||
    iteration?.scenarios.find((item) => item.id === run?.active_scenario) ||
    iteration?.scenarios.findLast((item) => item.status !== "pending") ||
    iteration?.scenarios[0];
  return { iteration, scenario, selectedNumber };
}

export function needsAttention(scenario: ScenarioObservation, threshold: number) {
  return (
    scenario.status === "error" ||
    (!!scenario.evaluation &&
      Object.values(scenario.evaluation.scores).some((score) => score < threshold))
  );
}
