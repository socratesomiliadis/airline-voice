"use client";

import { AudioLines, ChevronRight, Headphones, LockKeyhole, Plane, Radio } from "lucide-react";
import { usePathname } from "next/navigation";
import type { CSSProperties, ReactNode } from "react";
import { SidebarNavigation } from "@/components/layout/sidebar-navigation";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { useMonitoring } from "@/features/monitoring/monitoring-provider";

export function DashboardShell({ children }: { children: ReactNode }) {
  const { connection } = useMonitoring();
  const pathname = usePathname();
  const page =
    pathname === "/" ? "Overview" : pathname === "/conversations" ? "Conversations" : "Evaluations";
  return (
    <SidebarProvider style={{ "--sidebar-width": "232px" } as CSSProperties}>
      <a
        href="#main-content"
        className="sr-only rounded bg-background p-3 focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50"
      >
        Skip to content
      </a>
      <Sidebar collapsible="offcanvas" className="border-none">
        <SidebarHeader className="gap-8 px-5 pt-8 pb-6">
          <div className="flex items-center gap-3 px-1">
            <div className="flex size-9 items-center justify-center rounded-lg bg-white/10 text-white">
              <AudioLines className="size-5" aria-hidden="true" />
            </div>
            <span className="text-lg font-medium tracking-tight text-white">
              airline<span className="text-white/60">voice</span>
            </span>
          </div>
          <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3">
            <Plane className="size-4 text-teal-300" aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-white">Airline assistant</p>
              <p className="mt-1 text-xs text-white/50">Agent observability</p>
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup className="px-4">
            <SidebarGroupLabel className="mb-2 px-3 text-xs font-normal text-white/55">
              Workspace
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarNavigation />
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="gap-5 px-6 pb-6">
          <div className="flex items-start gap-2.5 border-t border-white/10 pt-5 text-white/50">
            <LockKeyhole className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <div>
              <p className="text-xs text-white/70">Observation only</p>
              <p className="mt-1.5 text-xs leading-5">
                The agent runs autonomously.
                <br />
                This workspace follows along.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-white/55">
            <Headphones className="size-3.5" aria-hidden="true" />
            ElevenLabs · Chat mode
          </div>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset className="min-w-0 bg-background">
        <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b bg-card px-5 sm:px-8 lg:px-10">
          <div className="flex min-w-0 items-center gap-3">
            <SidebarTrigger className="md:hidden" />
            <div className="flex items-center gap-2 text-xs sm:text-[13px]">
              <span className="text-muted-foreground">Observability</span>
              <ChevronRight className="size-3 text-muted-foreground/60" aria-hidden="true" />
              <span className="font-medium">{page}</span>
            </div>
          </div>
          <span
            role="status"
            className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground"
          >
            <Radio
              className={`size-3.5 ${connection === "connected" ? "text-primary" : "text-amber-600"}`}
              aria-hidden="true"
            />
            {connection === "connected"
              ? "Connected"
              : connection === "reconnecting"
                ? "Reconnecting"
                : "Connecting"}
          </span>
        </header>
        <div
          id="main-content"
          className="mx-auto w-full max-w-[1600px] min-w-0 px-5 py-8 sm:px-8 lg:px-10 lg:py-10"
        >
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
