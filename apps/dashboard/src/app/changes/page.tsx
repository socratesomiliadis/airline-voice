import type { Metadata } from "next";

import { MonitoringPage } from "@/features/monitoring/components/monitoring-page";

export const metadata: Metadata = { title: "Code & prompt changes" };

export default function Page() {
  return <MonitoringPage view="changes" />;
}
