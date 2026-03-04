"use client";

import dynamic from "next/dynamic";
import { useCallback, useRef, useState } from "react";
import ChatInterface from "@/components/ChatInterface";
import EventFeed from "@/components/EventFeed";
import { useEvents } from "@/hooks/useEvents";
import { useSSE } from "@/hooks/useSSE";
import type { MapFocusInstruction } from "@/lib/api";

const Map = dynamic(() => import("@/components/Map"), { ssr: false });

export default function Dashboard() {
  const { events, loading, refetch } = useEvents();
  const { connected } = useSSE(refetch);
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null);
  const [mapFocus, setMapFocus] = useState<MapFocusInstruction | null>(null);
  const [feedHeightPct, setFeedHeightPct] = useState(55);
  const rightPanelRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const handleMapFocus = useCallback((focus: MapFocusInstruction) => {
    setMapFocus(focus);
  }, []);

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
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-sentinel-500">
            SENTINEL
          </h1>
          <span className="text-xs text-gray-400">
            Disaster & Climate Risk Monitor
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div
              className={`w-2 h-2 rounded-full ${
                connected
                  ? "bg-green-500 animate-pulse-dot"
                  : "bg-red-500"
              }`}
            />
            <span className="text-xs text-gray-400">
              {connected ? "Live" : "Disconnected"}
            </span>
          </div>
          <span className="text-xs text-gray-500">
            {events.length} events
          </span>
        </div>
      </header>

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
