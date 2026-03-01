"use client";

interface SituationReportProps {
  region: string;
  severity: number;
  content: string;
  generatedAt: string;
}

const SEVERITY_LABELS = ["", "Minimal", "Low", "Moderate", "High", "Critical"];

export default function SituationReport({
  region,
  severity,
  content,
  generatedAt,
}: SituationReportProps) {
  const severityColor =
    severity >= 4
      ? "border-red-500 bg-red-950/30"
      : severity >= 3
      ? "border-amber-500 bg-amber-950/30"
      : "border-gray-700 bg-gray-900";

  return (
    <div className={`rounded-lg border-l-4 p-4 ${severityColor}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-bold text-gray-200">
          Situation Report: {region}
        </h3>
        <span className="text-xs text-gray-500">
          {new Date(generatedAt).toLocaleString()}
        </span>
      </div>
      <div className="flex items-center gap-2 mb-3">
        <span
          className={`text-xs px-2 py-0.5 rounded font-medium ${
            severity >= 4
              ? "bg-red-900/50 text-red-300"
              : severity >= 3
              ? "bg-amber-900/50 text-amber-300"
              : "bg-gray-800 text-gray-300"
          }`}
        >
          Severity: {SEVERITY_LABELS[severity]} ({severity}/5)
        </span>
      </div>
      <p className="text-sm text-gray-300 whitespace-pre-wrap">{content}</p>
    </div>
  );
}
