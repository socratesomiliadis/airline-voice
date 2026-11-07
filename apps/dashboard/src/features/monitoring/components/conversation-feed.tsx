"use client";

import {
  ArrowDown,
  Bot,
  CheckCheck,
  CircleAlert,
  MessagesSquare,
  Radio,
  UserRound,
  Wrench,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { label, time } from "@/features/monitoring/format";
import type { ScenarioObservation } from "@/lib/api/contracts";
import { ObservationEmpty, ObservationPanel } from "./observation-panel";

export function ConversationFeed({
  scenario,
  live,
}: {
  scenario?: ScenarioObservation;
  live: boolean;
}) {
  const scrollRoot = useRef<HTMLDivElement>(null);
  const viewport = useRef<HTMLDivElement | null>(null);
  const follow = useRef(true);
  const [detached, setDetached] = useState(false);
  const messageCount = scenario?.dialogue.length || 0;
  const lastMessage = scenario?.dialogue.at(-1)?.message;
  const selected = scenario?.conversation_id || scenario?.id;
  useEffect(() => {
    viewport.current =
      scrollRoot.current?.querySelector<HTMLDivElement>('[data-slot="scroll-area-viewport"]') ||
      null;
    return () => {
      viewport.current = null;
    };
  }, []);
  useEffect(() => {
    if (!messageCount && !lastMessage) return;
    if (viewport.current && follow.current)
      viewport.current.scrollTop = viewport.current.scrollHeight;
  }, [messageCount, lastMessage]);
  useEffect(() => {
    if (selected) {
      follow.current = true;
      setDetached(false);
      if (viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight;
    }
  }, [selected]);
  return (
    <ObservationPanel
      title="Conversation feed"
      icon={MessagesSquare}
      subtitle="Customer simulation & airline assistant"
      action={
        <Badge variant={live ? "default" : "outline"}>
          {live ? (
            <Radio className="motion-safe:animate-pulse" aria-hidden="true" />
          ) : (
            <CheckCheck aria-hidden="true" />
          )}
          {live ? "Live conversation" : scenario?.status === "pending" ? "Queued" : "Transcript"}
        </Badge>
      }
    >
      <div className="relative">
        <ScrollArea
          ref={scrollRoot}
          className="h-[390px] bg-muted/20"
          onScrollCapture={() => {
            const element = viewport.current;
            if (!element) return;
            follow.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
            setDetached(!follow.current);
          }}
        >
          <div
            role="log"
            aria-label="Conversation messages"
            aria-live={live && !detached ? "polite" : "off"}
            aria-relevant="additions text"
            className="px-5 py-5"
          >
            {!scenario?.dialogue.length ? (
              <ObservationEmpty
                title={live ? "Waiting for the first message" : "No conversation yet"}
                description="Messages appear here as the customer and airline assistant exchange turns."
              />
            ) : (
              <div className="space-y-5">
                {scenario.dialogue.map((message) => (
                  <div
                    key={`${scenario.id}-${message.role}-${message.occurred_at}`}
                    className={`flex gap-2.5 ${message.role === "user" ? "flex-row-reverse" : ""}`}
                  >
                    <Avatar size="sm" className="mt-0.5" aria-hidden="true">
                      <AvatarFallback
                        className={message.role === "agent" ? "bg-accent text-primary" : ""}
                      >
                        {message.role === "agent" ? (
                          <Bot className="size-3.5" />
                        ) : (
                          <UserRound className="size-3.5" />
                        )}
                      </AvatarFallback>
                    </Avatar>
                    <div className="max-w-[88%] min-w-0">
                      <div
                        className={`mb-1.5 flex flex-wrap items-center gap-2 text-[10px] ${message.role === "user" ? "justify-end" : ""}`}
                      >
                        <span className="font-medium text-muted-foreground">
                          {message.role === "agent"
                            ? "Avery · Airline assistant"
                            : "Customer · Simulated"}
                        </span>
                        <time dateTime={message.occurred_at} className="text-muted-foreground/60">
                          {time(message.occurred_at)}
                        </time>
                      </div>
                      <Card
                        size="sm"
                        className={`py-3 ${message.role === "agent" ? "rounded-tl-sm" : "rounded-tr-sm bg-primary text-primary-foreground"}`}
                      >
                        <CardContent>
                          <p className="whitespace-pre-wrap break-words text-[13px] leading-[1.75]">
                            {message.message}
                          </p>
                        </CardContent>
                      </Card>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {live && scenario?.dialogue.length ? (
              <Badge variant="outline" className="mt-5">
                <Radio className="motion-safe:animate-pulse" aria-hidden="true" />
                Conversation in progress
              </Badge>
            ) : null}
          </div>
        </ScrollArea>
        {detached && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              follow.current = true;
              setDetached(false);
              if (viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight;
            }}
            className="absolute right-4 bottom-3 rounded-full shadow-md"
          >
            <ArrowDown aria-hidden="true" />
            Follow messages
          </Button>
        )}
      </div>
      <div className="border-t px-5 py-3">
        {scenario?.tools.length ? (
          <Accordion multiple>
            {scenario.tools.map((tool) => (
              <AccordionItem key={tool.id} value={tool.id}>
                <AccordionTrigger className="py-2 text-[10px]">
                  <span className="flex items-center gap-2">
                    <Wrench className="size-3 text-muted-foreground" aria-hidden="true" />
                    <span className="font-mono">{tool.name}</span>
                    <Badge
                      variant={tool.status === "error" ? "destructive" : "outline"}
                      className="text-[9px]"
                    >
                      {label(tool.status)}
                    </Badge>
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  {tool.result ? (
                    <ScrollArea className="h-32">
                      <pre className="whitespace-pre-wrap break-all text-[10px] leading-5 text-muted-foreground">
                        {tool.result}
                      </pre>
                    </ScrollArea>
                  ) : (
                    <p className="text-xs text-muted-foreground">Awaiting tool result.</p>
                  )}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        ) : (
          <p className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <Wrench className="size-3" aria-hidden="true" />
            Tool activity will appear here
          </p>
        )}
        {scenario?.errors.map((error) => (
          <Alert key={error} variant="destructive" className="mt-2">
            <CircleAlert aria-hidden="true" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ))}
      </div>
    </ObservationPanel>
  );
}
