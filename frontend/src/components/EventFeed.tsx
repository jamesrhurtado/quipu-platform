"use client";

import type { Event } from "@/lib/api";

const SEVERITY_LABELS = ["", "Minimal", "Low", "Moderate", "High", "Critical"];
const SEVERITY_COLORS: Record<number, string> = {
  1: "text-gray-400 bg-gray-800",
  2: "text-blue-400 bg-blue-900/30",
  3: "text-amber-400 bg-amber-900/30",
  4: "text-orange-400 bg-orange-900/30",
  5: "text-red-400 bg-red-900/30",
};

const TYPE_ICONS: Record<string, string> = {
  earthquake: "⚡",
  wildfire: "🔥",
  flood: "🌊",
  cyclone: "🌀",
  volcano: "🌋",
  storm: "⛈️",
  drought: "☀️",
  landslide: "⛰️",
  ice: "🧊",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

interface EventFeedProps {
  events: Event[];
  loading: boolean;
  selectedEvent: string | null;
  onSelectEvent: (id: string) => void;
}

export default function EventFeed({
  events,
  loading,
  selectedEvent,
  onSelectEvent,
}: EventFeedProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-gray-800">
        <h2 className="text-sm font-semibold text-gray-300">Event Feed</h2>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
            Loading events...
          </div>
        ) : events.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
            No events found
          </div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {events.map((event) => (
              <button
                key={event.id}
                onClick={() => onSelectEvent(event.id)}
                className={`w-full text-left px-4 py-3 hover:bg-gray-800/50 transition-colors ${
                  selectedEvent === event.id ? "bg-gray-800/70" : ""
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg mt-0.5">
                    {TYPE_ICONS[event.event_type] || "⚠️"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-medium text-gray-200 truncate">
                        {event.title}
                      </h3>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded ${
                          SEVERITY_COLORS[event.severity]
                        }`}
                      >
                        {SEVERITY_LABELS[event.severity]}
                      </span>
                      <span className="text-xs text-gray-500">
                        {event.source.toUpperCase()}
                      </span>
                      {event.magnitude != null && (
                        <span className="text-xs text-gray-500">
                          M{event.magnitude.toFixed(1)}
                        </span>
                      )}
                      {event.created_at && (
                        <span className="text-xs text-gray-600">
                          {timeAgo(event.created_at)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
