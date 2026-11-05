/** Mirrors the Python event envelope. Generate API types once domain schemas exist. */
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface EventEnvelope {
  id: string;
  name: string;
  occurred_at: string;
  correlation_id: string;
  payload: Record<string, JsonValue>;
}
