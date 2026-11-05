import type { EventEnvelope, JsonValue } from "@/lib/api/contracts";

/** Future server-side API adapter. No fetches, mock responses, or polling exist yet. */
export interface MonitoringApi {
  listConversations(): Promise<Record<string, JsonValue>[]>;
  listEvaluations(): Promise<Record<string, JsonValue>[]>;
  listChanges(): Promise<Record<string, JsonValue>[]>;
  listIterations(): Promise<Record<string, JsonValue>[]>;
  listKnowledgeDocuments(): Promise<Record<string, JsonValue>[]>;
}

/** Transport choice, reconnects, replay, and authentication remain to be implemented. */
export interface MonitoringEventStream {
  subscribe(onEvent: (event: EventEnvelope) => void): () => void;
}
