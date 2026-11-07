import type { Metadata } from "next";
import { RefinementDashboard } from "@/features/monitoring/components/refinement-dashboard";

export const metadata: Metadata = { title: "Evaluations" };

export default async function Page({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const { tab } = await searchParams;
  return (
    <RefinementDashboard
      view="evaluations"
      tab={tab === "changes" || tab === "history" ? tab : "results"}
    />
  );
}
