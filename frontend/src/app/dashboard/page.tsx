"use client";

import dynamic from "next/dynamic";
import { useCallback, useRef, useState } from "react";
import AlertBanner from "@/components/AlertBanner";
import ChatInterface from "@/components/ChatInterface";
import EventFeed from "@/components/EventFeed";
import DashboardHeader from "@/components/DashboardHeader";
import { useEvents } from "@/hooks/useEvents";
import { useSSE } from "@/hooks/useSSE";
import type { AlertData, MapFocusInstruction } from "@/lib/api";

const Map = dynamic(() => import("@/components/Map"), { ssr: false });

export default function Dashboard() {
  const { events, loading, refetch } = useEvents();
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null);
  const [mapFocus, setMapFocus] = useState<MapFocusInstruction | null>(null);
  const [feedHeightPct, setFeedHeightPct] = useState(55);
  const rightPanelRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const [alerts, setAlerts] = useState<AlertData[]>([]);

  const handleMapFocus = useCallback((focus: MapFocusInstruction) => {
    setMapFocus(focus);
  }, []);

  const handleAlert = useCallback((alert: AlertData) => {
    setAlerts((prev) => [alert, ...prev]);
  }, []);

  const handleDismissAlert = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const { connected } = useSSE(refetch, handleAlert);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = true;

    const onMove = (ev: MouseEvent) => {
      if (!draggingRef.current || !rightPanelRef.current) return;
      const rect = rightPanelRef.current.getBoundingClientRect();
      const pct = ((ev.clientY - rect.top) / rect.height) * 100;
      setFeedHeightPct(Math.min(80, Math.max(20, pct)));
    };

    const onUp = () => {
      draggingRef.current = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  return (
    <div className="flex flex-col h-screen">
      {/* Alert Banners */}
      {alerts.map((alert) => (
        <AlertBanner
          key={alert.id}
          alert={alert}
          onDismiss={handleDismissAlert}
        />
      ))}

      {/* Header */}
      <DashboardHeader connected={connected} eventCount={events.length} />

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel — Map */}
        <div className="flex-1 relative">
          <Map
            events={events}
            selectedEvent={selectedEvent}
            onSelectEvent={setSelectedEvent}
            mapFocus={mapFocus}
          />
        </div>

        {/* Right panel — Feed + Chat */}
        <div
          ref={rightPanelRef}
          className="w-[420px] flex flex-col border-l border-gray-800 bg-gray-900"
        >
          {/* Event Feed */}
          <div
            className="overflow-hidden"
            style={{ height: `${feedHeightPct}%` }}
          >
            <EventFeed
              events={events}
              loading={loading}
              selectedEvent={selectedEvent}
              onSelectEvent={setSelectedEvent}
            />
          </div>

          {/* Drag handle */}
          <div
            onMouseDown={handleDragStart}
            className="h-1.5 bg-gray-800 hover:bg-sentinel-700 cursor-row-resize flex-shrink-0 transition-colors"
          />

          {/* Chat Interface */}
          <div className="flex-1 overflow-hidden border-t border-gray-800">
            <ChatInterface onMapFocus={handleMapFocus} />
          </div>
        </div>
      </div>
    </div>
  );
}
