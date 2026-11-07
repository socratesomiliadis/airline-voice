import { forwardMonitoring } from "@/lib/api/monitoring-server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export function GET(request: Request) {
  return forwardMonitoring(request, true);
}
