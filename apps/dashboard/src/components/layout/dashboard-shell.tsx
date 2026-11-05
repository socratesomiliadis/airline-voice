import { AudioLines, Plane, Unplug } from "lucide-react";
import type { ReactNode } from "react";

import { SidebarNavigation } from "@/components/layout/sidebar-navigation";

export function DashboardShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[240px_1fr]">
      <a
        href="#main-content"
        className="sr-only rounded bg-white p-3 focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50"
      >
        Skip to content
      </a>
      <aside className="flex flex-col border-r border-slate-200 bg-white lg:sticky lg:top-0 lg:h-screen">
        <div className="flex items-center gap-3 border-b border-slate-100 px-6 py-7">
          <div className="flex size-10 items-center justify-center rounded-xl bg-emerald-700 text-white">
            <Plane aria-hidden="true" className="size-5" />
          </div>
          <div>
            <p className="font-semibold tracking-tight">Airline Voice</p>
            <p className="mt-0.5 text-xs text-slate-500">Operations workspace</p>
          </div>
        </div>
        <div className="flex-1 px-4 py-6">
          <p className="mb-3 px-3 text-[10px] font-semibold tracking-[0.18em] text-slate-400 uppercase">
            Workspace
          </p>
          <SidebarNavigation />
        </div>
        <div className="m-4 hidden rounded-xl border border-slate-200 bg-slate-50 p-4 lg:block">
          <AudioLines aria-hidden="true" className="mb-3 size-5 text-slate-400" />
          <p className="text-xs font-medium">ElevenLabs integration</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">Awaiting implementation</p>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="flex min-h-20 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white/80 px-6 py-4 lg:px-10">
          <span className="text-sm text-slate-500">Customer service agent</span>
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-500">
            <Unplug aria-hidden="true" className="size-3.5" />
            Live data not connected
          </span>
        </header>
        <main id="main-content" className="mx-auto max-w-7xl px-6 py-10 lg:px-10">
          {children}
        </main>
      </div>
    </div>
  );
}
