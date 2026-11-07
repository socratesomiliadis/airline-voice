import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { PageHeading } from "@/components/ui/page-heading";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { type MonitoringView, monitoringViews } from "@/features/monitoring/view-definitions";

export function MonitoringPage({ view }: { view: MonitoringView }) {
  const definition = monitoringViews[view];
  const Icon = definition.icon;
  return (
    <>
      <PageHeading
        eyebrow="Monitoring"
        title={definition.title}
        description={definition.description}
      />
      <Card className="py-0" aria-label={definition.title}>
        <CardContent className="p-0">
          <Table className="min-w-[480px] text-xs">
            <TableCaption className="sr-only">
              {definition.title}; data is not connected
            </TableCaption>
            <TableHeader>
              <TableRow>
                {definition.columns.map((column) => (
                  <TableHead key={column} scope="col" className="px-6 py-4">
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell colSpan={definition.columns.length}>
                  <Empty className="min-h-64">
                    <EmptyHeader>
                      <EmptyMedia variant="icon">
                        <Icon aria-hidden="true" />
                      </EmptyMedia>
                      <EmptyTitle>{definition.emptyTitle}</EmptyTitle>
                      <EmptyDescription>{definition.emptyDescription}</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
