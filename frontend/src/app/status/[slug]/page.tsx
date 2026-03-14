"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchPublicStatus, PublicStatus } from "@/lib/api";

const LEVEL_COLORS: Record<string, string> = {
  Critical: "text-red-400",
  Elevated: "text-yellow-400",
  Normal: "text-green-400",
  Unknown: "text-gray-400",
};

const ALERT_LEVEL_STYLES: Record<string, string> = {
  critical: "bg-red-900/30 text-red-300 border-red-700",
  high: "bg-orange-900/30 text-orange-300 border-orange-700",
  elevated: "bg-yellow-900/30 text-yellow-300 border-yellow-700",
};

export default function PublicStatusPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [status, setStatus] = useState<PublicStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPublicStatus(slug)
      .then(setStatus)
      .catch(() => setError("Municipality not found or status unavailable."))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-950 text-gray-400">
        Loading status...
      </div>
    );
  }

  if (error || !status) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-950">
        <p className="text-gray-400 mb-4">{error || "Not found"}</p>
        <a href="/" className="text-sentinel-400 hover:text-sentinel-300 text-sm">
          &larr; Back to Quipu
        </a>
      </div>
    );
  }

  const riskColor = LEVEL_COLORS[status.risk.level] || LEVEL_COLORS.Unknown;

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="px-6 py-4 bg-gray-900 border-b border-gray-800">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div>
            <span className="text-sentinel-500 font-bold">Quipu</span>
            <span className="text-gray-500 text-sm ml-2">Public Status</span>
          </div>
          <a href="/" className="text-gray-400 hover:text-gray-200 text-sm">
            &larr; Home
          </a>
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {/* Municipality info */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-100">{status.municipality}</h1>
          {status.department && (
            <p className="text-gray-400 mt-1">{status.department}, Peru</p>
          )}
        </div>

        {/* Risk Status Card */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center mb-6">
          <p className="text-gray-500 text-sm mb-2">Current Risk Level</p>
          <p className={`text-4xl font-bold ${riskColor}`}>
            {status.risk.level}
          </p>
          {status.risk.score !== null && (
            <p className="text-gray-400 text-lg mt-1">
              Score: {status.risk.score}/5
            </p>
          )}
          {status.risk.explanation && (
            <p className="text-gray-500 text-sm mt-4 max-w-md mx-auto">
              {status.risk.explanation}
            </p>
          )}
          {status.risk.updated_at && (
            <p className="text-gray-600 text-xs mt-4">
              Last updated: {new Date(status.risk.updated_at).toLocaleString()}
            </p>
          )}
        </div>

        {/* Active Alerts */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-100">Active Alerts</h2>
            <span className={`text-2xl font-bold ${status.active_alerts > 0 ? "text-red-400" : "text-green-400"}`}>
              {status.active_alerts}
            </span>
          </div>
          {status.recent_alerts.length > 0 ? (
            <div className="space-y-2">
              {status.recent_alerts.map((a, i) => (
                <div key={i} className="flex items-center justify-between bg-gray-800 rounded-lg px-4 py-3">
                  <div>
                    <span
                      className={`px-2 py-0.5 rounded text-xs border font-medium mr-2 ${
                        ALERT_LEVEL_STYLES[a.alert_level] || "bg-gray-700 text-gray-400 border-gray-600"
                      }`}
                    >
                      {a.alert_level.toUpperCase()}
                    </span>
                    <span className="text-gray-300 text-sm">{a.region}</span>
                  </div>
                  <span className="text-gray-500 text-xs">
                    {new Date(a.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No recent alerts.</p>
          )}
        </div>

        {/* Footer note */}
        <p className="text-center text-gray-600 text-xs">
          Powered by Quipu — AI Early Warning System
        </p>
      </div>
    </div>
  );
}
