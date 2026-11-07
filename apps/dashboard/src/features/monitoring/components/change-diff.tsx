"use client";

import { FileCode2, FileText, Minus, Plus } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { diffLines, label } from "@/features/monitoring/format";
import type { IterationObservation } from "@/lib/api/contracts";
import { ObservationEmpty, ObservationPanel } from "./observation-panel";

function DiffContents({
  iteration,
  kind,
}: {
  iteration?: IterationObservation;
  kind: "prompt" | "code";
}) {
  const diff = kind === "prompt" ? iteration?.prompt_diff : iteration?.code_diff;
  const lines = diff ? diffLines(diff) : [];
  if (!diff)
    return (
      <ObservationEmpty
        title={kind === "prompt" ? "No prompt changes recorded" : "No code changes recorded"}
        description={
          iteration?.change_status === "none"
            ? "When an evaluation identifies a failure, the loop will generate a targeted fix and its diff will appear here."
            : iteration?.repair_error
              ? "The proposed repair was rejected. See its recovery details below."
              : `This repair did not include a ${kind} change.`
        }
      />
    );
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/50 px-5 py-2.5 text-xs">
        <span className="flex items-center gap-2 font-mono text-muted-foreground">
          <FileText className="size-3" aria-hidden="true" />
          {kind === "prompt" ? "prompts/agent/system.md" : "Diagnosed backend functions"}
        </span>
        <span className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono text-xs text-emerald-700">
            <Plus aria-label="Added lines" />
            {lines.filter((line) => line.kind === "added").length}
          </Badge>
          <Badge variant="outline" className="font-mono text-xs text-rose-600">
            <Minus aria-label="Removed lines" />
            {lines.filter((line) => line.kind === "removed").length}
          </Badge>
        </span>
      </div>
      <ScrollArea className="h-[350px]" aria-label={`${kind} diff`}>
        <pre className="min-w-full w-max py-2 text-[13px] leading-6">
          <code>
            {lines.map((line) => (
              <span
                key={line.id}
                className={`flex min-w-full ${line.kind === "added" ? "bg-emerald-50 text-emerald-900" : line.kind === "removed" ? "bg-rose-50 text-rose-800" : line.kind === "header" ? "bg-muted/50 text-muted-foreground" : "text-muted-foreground"}`}
              >
                <span
                  aria-hidden="true"
                  className="inline-block w-9 shrink-0 select-none border-r pr-2 text-right text-xs text-muted-foreground"
                >
                  {line.before}
                </span>
                <span
                  aria-hidden="true"
                  className="inline-block w-9 shrink-0 select-none border-r pr-2 text-right text-xs text-muted-foreground"
                >
                  {line.after}
                </span>
                <span className="flex w-7 shrink-0 items-center justify-center">
                  {line.kind === "added" ? (
                    <Plus className="size-3 text-emerald-500" aria-label="Added" />
                  ) : line.kind === "removed" ? (
                    <Minus className="size-3 text-rose-400" aria-label="Removed" />
                  ) : null}
                </span>
                <span className="pr-5">{line.text || " "}</span>
                {"\n"}
              </span>
            ))}
          </code>
        </pre>
      </ScrollArea>
    </>
  );
}

export function ChangeDiff({ iteration }: { iteration?: IterationObservation }) {
  return (
    <Tabs defaultValue="prompt" className="min-w-0">
      <ObservationPanel
        title="What changed"
        subtitle="Before and after, recorded automatically"
        icon={FileCode2}
        action={
          <TabsList aria-label="Change type">
            <TabsTrigger value="prompt" className="px-3 text-xs">
              Prompt
            </TabsTrigger>
            <TabsTrigger value="code" className="px-3 text-xs">
              Code
            </TabsTrigger>
          </TabsList>
        }
      >
        {iteration?.repair_explanation && (
          <div className="border-b px-5 py-4">
            <div className="mb-2 flex items-center gap-2">
              <Badge
                variant={
                  iteration.change_status === "applied"
                    ? "default"
                    : iteration.change_status === "rolled_back" ||
                        iteration.change_status === "recovery_failed"
                      ? "destructive"
                      : "secondary"
                }
              >
                {label(iteration.change_status)}
              </Badge>
              <span className="text-xs text-muted-foreground">
                After iteration {iteration.number}
              </span>
            </div>
            <p className="text-xs leading-6 text-muted-foreground">
              {iteration.repair_explanation}
            </p>
          </div>
        )}
        <TabsContent value="prompt">
          <DiffContents iteration={iteration} kind="prompt" />
        </TabsContent>
        <TabsContent value="code">
          <DiffContents iteration={iteration} kind="code" />
        </TabsContent>
        {iteration?.repair_error && (
          <Alert variant="destructive" className="rounded-none border-x-0 border-b-0">
            <AlertDescription>{iteration.repair_error}</AlertDescription>
          </Alert>
        )}
      </ObservationPanel>
    </Tabs>
  );
}
