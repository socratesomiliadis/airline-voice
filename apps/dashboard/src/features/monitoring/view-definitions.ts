import type { LucideIcon } from "lucide-react";
import { BookOpen, FileCode2, ListChecks, MessagesSquare, Repeat2 } from "lucide-react";

type ViewDefinition = {
  title: string;
  description: string;
  icon: LucideIcon;
  columns: readonly string[];
  emptyTitle: string;
  emptyDescription: string;
};

export const monitoringViews = {
  conversations: {
    title: "Conversations",
    description: "A workspace for customer conversations, transcripts, and tool activity.",
    icon: MessagesSquare,
    columns: ["Conversation", "Channel", "Status", "Started"],
    emptyTitle: "No conversations connected",
    emptyDescription: "Conversation ingestion and live updates are awaiting implementation.",
  },
  evaluations: {
    title: "Evaluations",
    description: "A workspace for scenario results, quality scores, and failure analysis.",
    icon: ListChecks,
    columns: ["Evaluation", "Scenario", "Result", "Iteration"],
    emptyTitle: "No evaluation results",
    emptyDescription: "Simulation, scoring, and quality thresholds have not been implemented.",
  },
  changes: {
    title: "Code & prompt changes",
    description: "A workspace for proposed fixes, diffs, and verification results.",
    icon: FileCode2,
    columns: ["Change", "Type", "Verification", "Iteration"],
    emptyTitle: "No changes proposed",
    emptyDescription:
      "Fix generation, patch application, and verification are awaiting implementation.",
  },
  iterations: {
    title: "Iteration history",
    description: "A workspace for refinement runs, progress, and convergence history.",
    icon: Repeat2,
    columns: ["Iteration", "Run", "Outcome", "Started"],
    emptyTitle: "No refinement iterations",
    emptyDescription: "The refinement pipeline is scaffolded and does not execute any stages yet.",
  },
  knowledge: {
    title: "Knowledge base",
    description: "A workspace for airline policies, source documents, and indexing status.",
    icon: BookOpen,
    columns: ["Document", "Source", "Index status", "Updated"],
    emptyTitle: "No knowledge sources connected",
    emptyDescription:
      "Document ingestion, embedding, indexing, and retrieval are awaiting implementation.",
  },
} as const satisfies Record<string, ViewDefinition>;

export type MonitoringView = keyof typeof monitoringViews;
