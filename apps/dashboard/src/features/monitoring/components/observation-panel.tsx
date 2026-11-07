import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";

/** Domain composition of installed shadcn Card primitives. */
export function ObservationPanel({
  title,
  subtitle,
  icon: Icon,
  action,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  icon: LucideIcon;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card
      className={`min-w-0 gap-0 overflow-hidden rounded-lg py-0 shadow-none ring-border ${className || ""}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-5">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-[15px] font-medium tracking-tight">
            <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
            {title}
          </h2>
          {subtitle && (
            <p className="mt-1.5 text-[13px] leading-5 text-muted-foreground">{subtitle}</p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <CardContent className="p-0">{children}</CardContent>
    </Card>
  );
}
export function ObservationEmpty({ title, description }: { title: string; description: string }) {
  return (
    <Empty className="min-h-48 px-6 py-8">
      <EmptyHeader>
        <EmptyTitle className="text-sm font-medium">{title}</EmptyTitle>
        <EmptyDescription className="max-w-sm text-[13px] leading-6">
          {description}
        </EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
