"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { acknowledgeAlert, AlertData, fetchAlerts } from "@/lib/api";
import { useAuth } from "@/lib/auth-provider";

const LEVEL_STYLES: Record<string, string> = {
  critical: "bg-red-900/30 text-red-300 border-red-700",
  high: "bg-orange-900/30 text-orange-300 border-orange-700",
  elevated: "bg-yellow-900/30 text-yellow-300 border-yellow-700",
};

export default function AlertHistoryPage() {
  const { orgContext } = useAuth();
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "unacknowledged">("all");

  const loadAlerts = useCallback(async () => {
    try {
      const params: { acknowledged?: boolean; limit?: number } = { limit: 100 };
      if (filter === "unacknowledged") params.acknowledged = false;
      const data = await fetchAlerts(params);
      setAlerts(data.alerts);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  const handleAcknowledge = async (id: string) => {
    try {
      await acknowledgeAlert(id);
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a))
      );
    } catch {
      // silent
    }
  };

  return (
    <div className="min-h-screen bg-gray-950">
      <header className="flex items-center justify-between px-6 py-3 bg-gray-900 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="text-gray-400 hover:text-gray-200 text-sm">
            &larr; Dashboard
          </Link>
          <h1 className="text-lg font-bold text-gray-100">Alert History</h1>
        </div>
        {orgContext && (
          <span className="text-sm text-gray-400">{orgContext.municipality}</span>
        )}
      </header>

      <div className="max-w-5xl mx-auto p-6">
        {/* Filters */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              filter === "all" ? "bg-gray-700 text-gray-100" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter("unacknowledged")}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              filter === "unacknowledged" ? "bg-gray-700 text-gray-100" : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            Unacknowledged
          </button>
        </div>

        {loading ? (
          <p className="text-gray-400">Loading alerts...</p>
        ) : alerts.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500">No alerts found.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className="bg-gray-900 border border-gray-800 rounded-lg px-5 py-4"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`px-2 py-0.5 rounded text-xs border font-medium ${
                          LEVEL_STYLES[alert.alert_level] || "bg-gray-800 text-gray-400 border-gray-700"
                        }`}
                      >
                        {alert.alert_level.toUpperCase()}
                      </span>
                      <span className="text-gray-400 text-xs">
                        {new Date(alert.created_at).toLocaleString()}
                      </span>
                      {alert.acknowledged && (
                        <span className="text-green-500 text-xs">Acknowledged</span>
                      )}
                    </div>
                    <p className="text-gray-200 text-sm font-medium">{alert.region}</p>
                    <p className="text-gray-400 text-xs mt-1">
                      Risk score: {alert.risk_score}/5 ({alert.risk_level})
                    </p>
                    {alert.explanation && (
                      <p className="text-gray-500 text-xs mt-1 line-clamp-2">{alert.explanation}</p>
                    )}
                    {alert.drivers && alert.drivers.length > 0 && (
                      <div className="flex gap-2 mt-2">
                        {alert.drivers.map((d, i) => (
                          <span key={i} className="text-[10px] px-1.5 py-0.5 bg-gray-800 text-gray-400 rounded">
                            {d.label}: {d.value}/5
                          </span>
                        ))}
                      </div>
                    )}
                    {alert.actions_taken && alert.actions_taken.length > 0 && (
                      <div className="flex gap-2 mt-2">
                        {alert.actions_taken.map((a, i) => (
                          <span
                            key={i}
                            className={`text-[10px] px-1.5 py-0.5 rounded ${
                              a.status === "sent" ? "bg-green-900/30 text-green-400"
                                : a.status === "failed" ? "bg-red-900/30 text-red-400"
                                : "bg-gray-800 text-gray-500"
                            }`}
                          >
                            {a.label}: {a.status}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  {!alert.acknowledged && (
                    <button
                      onClick={() => handleAcknowledge(alert.id)}
                      className="ml-4 px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors whitespace-nowrap"
                    >
                      Acknowledge
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
