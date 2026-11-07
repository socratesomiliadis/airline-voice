import type { MonitoringSnapshot } from "@/lib/api/contracts";

export type ConnectionStatus = "connecting" | "connected" | "reconnecting";
export interface MonitoringState extends MonitoringSnapshot {
  connection: ConnectionStatus;
  receivedAt: number | null;
  selectedRun: string;
  selectRun: (runId: string) => void;
}
