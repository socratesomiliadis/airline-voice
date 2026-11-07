"use client";

import { createContext, type ReactNode, useContext, useEffect, useState } from "react";
import type { MonitoringSnapshot } from "@/lib/api/contracts";
import type { ConnectionStatus, MonitoringState } from "@/lib/api/ports";

const MonitoringContext = createContext<MonitoringState | null>(null);

export function MonitoringProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<MonitoringSnapshot>({ runs: [], run: null });
  const [connection, setConnection] = useState<ConnectionStatus>("connecting");
  const [receivedAt, setReceivedAt] = useState<number | null>(null);
  const [selectedRun, selectRun] = useState("");

  useEffect(() => {
    setConnection("connecting");
    // Selection only changes what is observed. The browser never sends commands to the loop.
    const url = selectedRun
      ? `/api/monitoring?run_id=${encodeURIComponent(selectedRun)}`
      : "/api/monitoring";
    let stream: EventSource;
    let lastEvent = Date.now();
    let stopped = false;
    const connect = () => {
      if (stopped) return;
      lastEvent = Date.now();
      stream = new EventSource(url);
      stream.addEventListener("snapshot", (event: MessageEvent<string>) => {
        try {
          const data: MonitoringSnapshot = JSON.parse(event.data);
          if (!Array.isArray(data.runs) || !("run" in data)) throw new Error("Invalid snapshot");
          lastEvent = Date.now();
          setSnapshot(data);
          setReceivedAt(lastEvent);
          setConnection("connected");
        } catch {
          setConnection("reconnecting");
        }
      });
      stream.addEventListener("heartbeat", () => {
        lastEvent = Date.now();
      });
      stream.addEventListener("unavailable", () => selectRun(""));
      stream.onerror = () => setConnection("reconnecting");
    };
    connect();
    const watchdog = setInterval(() => {
      if (Date.now() - lastEvent > 25_000) {
        stream.close();
        setConnection("reconnecting");
        connect();
      }
    }, 5_000);
    return () => {
      stopped = true;
      clearInterval(watchdog);
      stream.close();
    };
  }, [selectedRun]);

  return (
    <MonitoringContext.Provider
      value={{ ...snapshot, connection, receivedAt, selectedRun, selectRun }}
    >
      {children}
    </MonitoringContext.Provider>
  );
}

export function useMonitoring() {
  const state = useContext(MonitoringContext);
  if (!state) throw new Error("MonitoringProvider is required");
  return state;
}
