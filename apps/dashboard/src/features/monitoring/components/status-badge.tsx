import { Check, Circle, CircleAlert, Clock3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { label } from "@/features/monitoring/format";

export function StatusBadge({ status }: { status: string }) {
  const good = status === "passed" || status === "applied";
  const bad = [
    "error",
    "failed",
    "rolled_back",
    "recovery_failed",
    "iteration_limit",
    "stale",
  ].includes(status);
  const waiting = status === "pending" || status === "none";
  const Icon = good ? Check : bad ? CircleAlert : waiting ? Clock3 : Circle;
  return (
    <Badge
      variant="outline"
      className={`h-6 gap-1.5 border-transparent px-2 text-xs font-normal ${good ? "bg-emerald-50 text-emerald-800" : bad ? "bg-amber-50 text-amber-800" : waiting ? "bg-muted text-muted-foreground" : "bg-accent text-primary"}`}
    >
      <Icon className="size-3" aria-hidden="true" />
      {label(status)}
    </Badge>
  );
}
