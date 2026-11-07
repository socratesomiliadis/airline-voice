import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
    <Card className={`min-w-0 gap-0 overflow-hidden py-0 ${className || ""}`}>
      <CardHeader className="border-b py-4">
        <CardTitle>
          <h2 className="flex items-center gap-2 text-sm">
            <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
            {title}
          </h2>
        </CardTitle>
        {subtitle && <CardDescription className="text-xs">{subtitle}</CardDescription>}
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className="p-0">{children}</CardContent>
    </Card>
  );
}
export function ObservationEmpty({ title, description }: { title: string; description: string }) {
  return (
    <Empty className="min-h-44">
      <EmptyHeader>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription className="text-xs leading-6">{description}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
