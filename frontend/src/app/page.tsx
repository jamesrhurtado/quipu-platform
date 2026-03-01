"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
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

  const handleMapFocus = useCallback((focus: MapFocusInstruction) => {
    setMapFocus(focus);
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
        <div className="w-[420px] flex flex-col border-l border-gray-800 bg-gray-900">
          {/* Event Feed */}
          <div className="flex-1 overflow-hidden">
            <EventFeed
              events={events}
              loading={loading}
              selectedEvent={selectedEvent}
              onSelectEvent={setSelectedEvent}
            />
          </div>

          {/* Chat Interface */}
          <div className="h-[45%] border-t border-gray-800">
            <ChatInterface onMapFocus={handleMapFocus} />
          </div>
        </div>
      </div>
    </div>
  );
}
