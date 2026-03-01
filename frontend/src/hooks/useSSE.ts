import { useEffect, useRef, useState } from "react";
import { createSSEConnection } from "@/lib/api";

export function useSSE(onNewEvent?: () => void) {
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
  }, [onNewEvent]);

  return { connected };
}
