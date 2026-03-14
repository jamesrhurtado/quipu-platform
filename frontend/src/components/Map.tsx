"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet.markercluster";
import type { Event, MapFocusInstruction } from "@/lib/api";
import { useAuth } from "@/lib/auth-provider";
import { fetchSettings } from "@/lib/api";

const SEVERITY_COLORS: Record<number, string> = {
  1: "#6b7280", // gray
  2: "#3b82f6", // blue
  3: "#f59e0b", // amber
  4: "#f97316", // orange
  5: "#ef4444", // red
};

const EVENT_ICONS: Record<string, string> = {
  earthquake: "⚡",
  wildfire: "🔥",
  flood: "🌊",
  cyclone: "🌀",
  volcano: "🌋",
  storm: "⛈️",
  drought: "☀️",
  landslide: "⛰️",
};

function createMarkerIcon(severity: number, eventType: string): L.DivIcon {
  const color = SEVERITY_COLORS[severity] || SEVERITY_COLORS[1];
  const icon = EVENT_ICONS[eventType] || "⚠️";
  const size = severity >= 4 ? 32 : severity >= 3 ? 26 : 20;

  return L.divIcon({
    className: "custom-marker",
    html: `<div style="
      background: ${color};
      width: ${size}px;
      height: ${size}px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: ${size * 0.5}px;
      border: 2px solid rgba(255,255,255,0.3);
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
      cursor: pointer;
    ">${icon}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

interface MapProps {
  events: Event[];
  selectedEvent: string | null;
  onSelectEvent: (id: string | null) => void;
  mapFocus?: MapFocusInstruction | null;
}

export default function Map({ events, selectedEvent, onSelectEvent, mapFocus }: MapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const clusterRef = useRef<L.MarkerClusterGroup | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { orgContext } = useAuth();

  // Initialize map — use org center/zoom if available
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const center: [number, number] = orgContext
      ? [orgContext.map_center_lat, orgContext.map_center_lon]
      : [-10, -65];
    const zoom = orgContext?.map_zoom ?? 4;

    const map = L.map(containerRef.current, {
      center,
      zoom,
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 18,
    }).addTo(map);

    const cluster = L.markerClusterGroup({
      maxClusterRadius: 40,
      spiderfyOnMaxZoom: true,
      showCoverageOnHover: false,
      iconCreateFunction: (clusterObj) => {
        const count = clusterObj.getChildCount();
        const markers = clusterObj.getAllChildMarkers();
        const maxSeverity = Math.max(
          ...markers.map((m: any) => m.options.severity || 1)
        );
        const color = SEVERITY_COLORS[maxSeverity] || SEVERITY_COLORS[1];

        return L.divIcon({
          className: "custom-cluster",
          html: `<div style="
            background: ${color};
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: bold;
            color: white;
            border: 2px solid rgba(255,255,255,0.4);
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
          ">${count}</div>`,
          iconSize: [36, 36],
          iconAnchor: [18, 18],
        });
      },
    });

    map.addLayer(cluster);
    mapRef.current = map;
    clusterRef.current = cluster;

    // Draw monitored zone boundaries if available
    if (orgContext) {
      fetchSettings()
        .then((s) => {
          for (const zone of s.monitored_zones) {
            const bounds: L.LatLngBoundsExpression = [
              [zone.bbox.min_lat, zone.bbox.min_lon],
              [zone.bbox.max_lat, zone.bbox.max_lon],
            ];
            L.rectangle(bounds, {
              color: zone.is_primary ? "#f59e0b" : "#6b7280",
              weight: 1.5,
              opacity: 0.6,
              fillOpacity: 0.05,
              dashArray: zone.is_primary ? undefined : "6 4",
            }).addTo(map).bindTooltip(zone.name, { permanent: false, direction: "center" });
          }
        })
        .catch(() => {}); // Non-critical, fail silently
    }

    return () => {
      map.remove();
      mapRef.current = null;
      clusterRef.current = null;
    };
  }, []);

  // Update markers when events change
  useEffect(() => {
    if (!clusterRef.current) return;
    clusterRef.current.clearLayers();

    for (const event of events) {
      const marker = L.marker([event.lat, event.lon], {
        icon: createMarkerIcon(event.severity, event.event_type),
        severity: event.severity,
      } as any);

      const magText =
        event.magnitude != null ? `<br/>Magnitude: ${event.magnitude}` : "";
      const timeText = event.started_at
        ? `<br/>Time: ${new Date(event.started_at).toLocaleString()}`
        : "";

      marker.bindPopup(`
        <div style="min-width: 200px;">
          <h3 style="font-size: 14px; font-weight: bold; margin: 0 0 8px 0;">
            ${event.title}
          </h3>
          <div style="font-size: 12px; color: #9ca3af;">
            Source: ${event.source.toUpperCase()}${magText}${timeText}
            <br/>Severity: ${"●".repeat(event.severity)}${"○".repeat(5 - event.severity)}
            ${event.description ? `<br/><br/>${event.description}` : ""}
          </div>
        </div>
      `);

      marker.on("click", () => onSelectEvent(event.id));
      clusterRef.current!.addLayer(marker);
    }
  }, [events, onSelectEvent]);

  // Pan to selected event
  useEffect(() => {
    if (!mapRef.current || !selectedEvent) return;
    const event = events.find((e) => e.id === selectedEvent);
    if (event) {
      mapRef.current.flyTo([event.lat, event.lon], 8, { duration: 1 });
    }
  }, [selectedEvent, events]);

  // Fly to map focus from agent response
  useEffect(() => {
    if (!mapRef.current || !mapFocus) return;
    mapRef.current.flyTo(
      [mapFocus.center_lat, mapFocus.center_lon],
      mapFocus.zoom,
      { duration: 1.5 }
    );
  }, [mapFocus]);

  return <div ref={containerRef} className="w-full h-full" />;
}
