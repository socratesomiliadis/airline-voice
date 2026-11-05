import { EmptyState } from "@/components/ui/empty-state";
import { PageHeading } from "@/components/ui/page-heading";
import { type MonitoringView, monitoringViews } from "@/features/monitoring/view-definitions";

export function MonitoringPage({ view }: { view: MonitoringView }) {
  const definition = monitoringViews[view];

  return (
    <>
      <PageHeading
        eyebrow="Monitoring"
        title={definition.title}
        description={definition.description}
      />
      <section
        aria-label={definition.title}
        className="overflow-hidden rounded-2xl border border-slate-200 bg-white"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-left text-xs">
            <caption className="sr-only">{definition.title}; data is not connected</caption>
            <thead className="border-b border-slate-100 bg-slate-50/70 text-slate-500">
              <tr>
                {definition.columns.map((column) => (
                  <th key={column} scope="col" className="px-6 py-4 font-medium">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={definition.columns.length}>
                  <EmptyState
                    icon={definition.icon}
                    title={definition.emptyTitle}
                    description={definition.emptyDescription}
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
