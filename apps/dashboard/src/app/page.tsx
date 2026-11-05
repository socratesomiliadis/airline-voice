import { ArrowUpRight, Blocks, Cable, Database, Workflow } from "lucide-react";
import Link from "next/link";

import { PageHeading } from "@/components/ui/page-heading";
import { monitoringViews } from "@/features/monitoring/view-definitions";

const foundations = [
  {
    title: "Voice & customer service",
    description: "ElevenLabs and airline service boundaries",
    icon: Cable,
  },
  {
    title: "Persistent data",
    description: "PostgreSQL, migrations, and repository interfaces",
    icon: Database,
  },
  {
    title: "Refinement pipeline",
    description: "Simulation through verification and iteration",
    icon: Workflow,
  },
];

export default function OverviewPage() {
  return (
    <>
      <PageHeading
        eyebrow="Operations overview"
        title="Agent workspace"
        description="Monitor conversations and the refinement process as the platform takes shape. This dashboard currently contains interface scaffolding."
      />
      <section className="mb-8 flex gap-4 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-6">
        <Blocks aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-emerald-700" />
        <div>
          <h2 className="text-sm font-semibold text-emerald-950">Foundation stage</h2>
          <p className="mt-1 text-sm leading-6 text-emerald-900/70">
            Service boundaries and monitoring views are in place. Live connections and the
            refinement workflow are awaiting implementation.
          </p>
        </div>
      </section>
      <section aria-label="Platform foundations" className="mb-10 grid gap-4 md:grid-cols-3">
        {foundations.map(({ title, description, icon: Icon }) => (
          <article key={title} className="rounded-2xl border border-slate-200 bg-white p-6">
            <Icon aria-hidden="true" className="mb-5 size-5 text-slate-400" />
            <h2 className="text-sm font-semibold">{title}</h2>
            <p className="mt-2 text-xs leading-5 text-slate-500">{description}</p>
            <p className="mt-5 text-[11px] font-medium tracking-wide text-slate-400 uppercase">
              Scaffolded
            </p>
          </article>
        ))}
      </section>
      <h2 className="mb-4 text-sm font-semibold">Explore the workspace</h2>
      <div className="grid gap-3 md:grid-cols-2">
        {Object.entries(monitoringViews).map(([key, { title, description, icon: Icon }]) => (
          <Link
            key={key}
            href={`/${key}`}
            className="group flex items-start gap-4 rounded-xl border border-slate-200 bg-white p-5 transition-colors hover:border-emerald-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
          >
            <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-slate-400" />
            <div className="flex-1">
              <h3 className="text-sm font-medium">{title}</h3>
              <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
            </div>
            <ArrowUpRight
              aria-hidden="true"
              className="size-4 shrink-0 text-slate-300 group-hover:text-emerald-700"
            />
          </Link>
        ))}
      </div>
    </>
  );
}
