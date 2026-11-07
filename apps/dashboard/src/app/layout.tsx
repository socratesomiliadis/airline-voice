import type { Metadata } from "next";
import type { ReactNode } from "react";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { MonitoringProvider } from "@/features/monitoring/monitoring-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Airline Voice · Operations",
    template: "%s · Airline Voice",
  },
  description: "Observe autonomous airline conversations, evaluation scores and improvements live.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="font-sans">
      <body className="min-h-screen bg-[#f8faf9] font-sans text-slate-900 antialiased">
        <TooltipProvider>
          <MonitoringProvider>
            <DashboardShell>{children}</DashboardShell>
          </MonitoringProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
