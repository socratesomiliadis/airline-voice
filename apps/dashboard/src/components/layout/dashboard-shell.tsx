"use client";

import { Eye, LockKeyhole, Plane, Radio, Workflow } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { SidebarNavigation } from "@/components/layout/sidebar-navigation";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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
  return (
    <SidebarProvider style={{ "--sidebar-width": "218px" } as CSSProperties}>
      <a
        href="#main-content"
        className="sr-only rounded bg-background p-3 focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50"
      >
        Skip to content
      </a>
      <Sidebar collapsible="offcanvas">
        <SidebarHeader className="gap-5 p-5">
          <div className="flex items-center gap-2.5 py-2">
            <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Plane aria-hidden="true" className="size-4.5 -rotate-12" />
            </div>
            <div>
              <p className="text-[15px] font-semibold tracking-tight">
                airline<span className="font-normal text-muted-foreground">voice</span>
              </p>
              <p className="mt-0.5 text-[9px] tracking-wider text-muted-foreground">
                AUTONOMOUS AGENT LAB
              </p>
            </div>
          </div>
          <Badge
            variant="outline"
            className="h-auto justify-start gap-2 rounded-lg px-3 py-2.5 text-[11px]"
          >
            <Workflow className="size-3" aria-hidden="true" />
            Airline assistant
          </Badge>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Observe</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarNavigation />
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="gap-4 p-4">
          <Card size="sm" className="bg-accent/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xs text-primary">
                <Eye className="size-4" aria-hidden="true" />
                Autonomous by design
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-[10px] leading-5 text-muted-foreground">
                The agent simulates, evaluates and improves itself. You have a front-row seat.
              </p>
              <Badge variant="outline" className="gap-1.5 text-[9px]">
                <LockKeyhole className="size-3" aria-hidden="true" />
                Read-only workspace
              </Badge>
            </CardContent>
          </Card>
          <Separator />
          <p className="text-center text-[10px] text-muted-foreground">ElevenLabs · Chat Mode</p>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset className="min-w-0 bg-[#f8faf9]">
        <header className="flex min-h-[68px] flex-wrap items-center justify-between gap-3 border-b bg-background/80 px-5 py-3 sm:px-8">
          <div className="flex items-center gap-3">
            <SidebarTrigger className="md:hidden" />
            <Breadcrumb>
              <BreadcrumbList className="text-[11px]">
                <BreadcrumbItem>Workspace</BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>Agent observatory</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden text-[10px] text-muted-foreground sm:inline">
              Autonomous refinement loop
            </span>
            <Badge
              role="status"
              variant={
                connection === "connected"
                  ? "default"
                  : connection === "reconnecting"
                    ? "secondary"
                    : "outline"
              }
              className="h-7 gap-1.5 px-2.5 text-[10px]"
            >
              <Radio
                className={connection === "connecting" ? "motion-safe:animate-pulse" : ""}
                aria-hidden="true"
              />
              {connection === "connected"
                ? "Live updates"
                : connection === "reconnecting"
                  ? "Reconnecting"
                  : "Connecting"}
            </Badge>
          </div>
        </header>
        <div id="main-content" className="mx-auto w-full max-w-[1560px] px-4 py-7 sm:px-8 sm:py-8">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
