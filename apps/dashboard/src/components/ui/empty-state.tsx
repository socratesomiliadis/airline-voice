import type { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-5 flex size-12 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-400">
        <Icon aria-hidden="true" className="size-5" />
      </div>
      <p className="text-sm font-medium text-slate-700">{title}</p>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p>
    </div>
  );
}
