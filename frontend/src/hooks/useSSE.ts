import { useEffect, useRef, useState } from "react";
import { AlertData, createSSEConnection } from "@/lib/api";

export function useSSE(onNewEvent?: () => void, onAlert?: (alert: AlertData) => void) {
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const onNewEventRef = useRef(onNewEvent);
  const onAlertRef = useRef(onAlert);

  // Keep refs up to date without re-triggering the effect
  onNewEventRef.current = onNewEvent;
  onAlertRef.current = onAlert;

  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let disposed = false;

    async function connect() {
      if (disposed) return;

      try {
        const es = await createSSEConnection(
          (event, data) => {
            if (event === "connected") {
              setConnected(true);
            } else if (event === "new_event" || event === "new_events_batch") {
              onNewEventRef.current?.();
            } else if (event === "poll_complete") {
              onNewEventRef.current?.();
            } else if (event === "alert") {
              onAlertRef.current?.(data as AlertData);
            }
          },
          () => {
            setConnected(false);
            // Auto-reconnect after 5 seconds
            if (!disposed) {
              reconnectTimer = setTimeout(connect, 5000);
            }
          }
        );
        esRef.current = es;
      } catch {
        // Failed to create connection, retry
        if (!disposed) {
          reconnectTimer = setTimeout(connect, 5000);
        }
      }
    }

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      esRef.current?.close();
      esRef.current = null;
    };
  }, []); // No dependencies — refs handle updates

  return { connected };
}
