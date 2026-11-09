/** Mirrors airline_contracts.monitoring; all data comes from read-only snapshots. */
export type RunStatus = "running" | "passed" | "iteration_limit" | "error";
export type Stage =
  | "preparing"
  | "simulating"
  | "evaluating"
  | "repairing"
  | "verifying"
  | "reloading"
  | "publishing"
  | "rollback"
  | "completed"
  | "error";
export type Criterion =
  | "understanding"
  | "api_correctness"
  | "outcome_confirmation"
  | "naturalness";
export type Scores = Record<Criterion, number>;
export interface Failure {
  criterion: Criterion;
  root_cause: "prompt" | "code" | "infrastructure";
  quote: string;
  explanation: string;
  code_faults: { path: string; function: string; behavior: string }[];
}
export interface Evaluation {
  scenario_id: string;
  scores: Scores;
  rationale: string;
  failures: Failure[];
  checks?: {
    name: string;
    passed: boolean;
    explanation: string;
    evidence: string;
    criteria?: Criterion[];
  }[];
}
export interface ScenarioObservation {
  id: string;
  goal: string;
  status: "pending" | "simulating" | "evaluating" | "passed" | "failed" | "error";
  conversation_id: string | null;
  dialogue: { role: "user" | "agent"; message: string; occurred_at: string }[];
  tools: { id: string; name: string; status: string; result: string | null }[];
  evaluation: Evaluation | null;
  errors: string[];
}
export interface IterationObservation {
  number: number;
  started_at: string;
  finished_at: string | null;
  stage: Stage;
  scenarios: ScenarioObservation[];
  prompt_diff: string;
  code_diff: string;
  change_status: "none" | "proposed" | "applied" | "rolled_back" | "recovery_failed";
  repair_explanation: string | null;
  repair_error: string | null;
}
export interface RunSummary {
  run_id: string;
  status: RunStatus;
  stage: Stage;
  started_at: string;
  updated_at: string;
  heartbeat_at: string;
  iteration: number;
  max_iterations: number;
  pass_score: number;
  scenario_count: number;
  active_scenario: string | null;
  error: string | null;
}
export interface RunObservation extends RunSummary {
  revision: number;
  iterations: IterationObservation[];
}
export interface MonitoringSnapshot {
  runs: RunSummary[];
  run: RunObservation | null;
}
