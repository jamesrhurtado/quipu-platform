"use client";

import { useEffect, useState } from "react";
import type { AlertData } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const LEVEL_STYLES: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  elevated: {
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    text: "text-amber-400",
    icon: "\u26A0",
  },
  high: {
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    text: "text-orange-400",
    icon: "\u26A0",
  },
  critical: {
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    text: "text-red-400",
    icon: "\uD83D\uDEA8",
  },
};

interface AlertBannerProps {
  alert: AlertData;
  onDismiss: (id: string) => void;
}

export default function AlertBanner({ alert, onDismiss }: AlertBannerProps) {
  const [visible, setVisible] = useState(true);
  const style = LEVEL_STYLES[alert.alert_level] || LEVEL_STYLES.elevated;

  // Auto-dismiss after 60s for elevated, 120s for high, never for critical
  useEffect(() => {
    if (alert.alert_level === "critical") return;
    const ms = alert.alert_level === "elevated" ? 60000 : 120000;
    const timer = setTimeout(() => handleDismiss(), ms);
    return () => clearTimeout(timer);
  }, [alert.alert_level]);

  const handleDismiss = async () => {
    setVisible(false);
    try {
      await fetch(`${API_BASE}/api/alerts/${alert.id}/acknowledge`, {
        method: "PATCH",
      });
    } catch {
      // Best effort
    }
    onDismiss(alert.id);
  };

  if (!visible) return null;

  return (
    <div
      className={`w-full px-4 py-2 ${style.bg} ${style.border} border-b flex items-center gap-3`}
    >
      <span className="text-lg flex-shrink-0">{style.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold uppercase ${style.text}`}>
            {alert.alert_level} ALERT
          </span>
          <span className="text-xs text-gray-400">
            {alert.region} — Risk {alert.risk_score.toFixed(1)}/5
          </span>
        </div>
        <p className="text-xs text-gray-400 truncate">{alert.explanation}</p>
        {alert.actions_taken && alert.actions_taken.length > 0 && (
          <div className="flex gap-2 mt-0.5 flex-wrap">
            {alert.actions_taken.map((action, i) => {
              const statusDot =
                action.status === "sent"
                  ? "bg-green-400"
                  : action.status === "failed"
                    ? "bg-red-400"
                    : "bg-gray-400";
              const statusLabel =
                action.status === "sent"
                  ? "Sent"
                  : action.status === "failed"
                    ? "Failed"
                    : "Simulated";
              const channelIcon =
                action.type === "teams"
                  ? "\uD83D\uDFEA"
                  : action.type === "bluesky"
                    ? "\uD83E\uDD4B"
                    : "\u2709\uFE0F";
              return (
                <span
                  key={i}
                  className="text-[10px] text-gray-400 bg-gray-800/50 px-1.5 py-0.5 rounded inline-flex items-center gap-1"
                >
                  <span>{channelIcon}</span>
                  <span>{action.label}</span>
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${statusDot}`} />
                  <span className="text-gray-500">{statusLabel}</span>
                </span>
              );
            })}
          </div>
        )}
      </div>
      <button
        onClick={handleDismiss}
        className={`text-xs ${style.text} hover:opacity-80 flex-shrink-0 px-2 py-1`}
      >
        Dismiss
      </button>
    </div>
  );
}
