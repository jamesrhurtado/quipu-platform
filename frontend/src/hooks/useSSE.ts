import { useEffect, useRef, useState } from "react";
import { AlertData, createSSEConnection } from "@/lib/api";

export function useSSE(onNewEvent?: () => void, onAlert?: (alert: AlertData) => void) {
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = createSSEConnection(
      (event, data) => {
        if (event === "connected") {
          setConnected(true);
        } else if (event === "new_event" || event === "new_events_batch") {
          onNewEvent?.();
        } else if (event === "poll_complete") {
          onNewEvent?.();
        } else if (event === "alert") {
          onAlert?.(data as AlertData);
        }
      },
      () => {
        setConnected(false);
      }
    );
    esRef.current = es;

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [onNewEvent, onAlert]);

  return { connected };
}
