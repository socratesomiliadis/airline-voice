import type { Metadata } from "next";

import { RefinementDashboard } from "@/features/monitoring/components/refinement-dashboard";

export const metadata: Metadata = { title: "Conversations" };

export default function Page() {
  return <RefinementDashboard view="conversations" />;
}
