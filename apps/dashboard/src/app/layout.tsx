import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DashboardShell } from "@/components/layout/dashboard-shell";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Airline Voice · Operations",
    template: "%s · Airline Voice",
  },
  description: "Monitoring workspace for the airline customer service agent.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 font-sans text-slate-900 antialiased">
        <DashboardShell>{children}</DashboardShell>
      </body>
    </html>
  );
}
