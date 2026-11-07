import type { Metadata } from "next";

import { RefinementDashboard } from "@/features/monitoring/components/refinement-dashboard";

export const metadata: Metadata = { title: "Evaluations" };

export default function Page() {
  return <RefinementDashboard view="evaluations" />;
}
