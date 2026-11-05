import type { Metadata } from "next";

import { MonitoringPage } from "@/features/monitoring/components/monitoring-page";

export const metadata: Metadata = { title: "Knowledge base" };

export default function Page() {
  return <MonitoringPage view="knowledge" />;
}
