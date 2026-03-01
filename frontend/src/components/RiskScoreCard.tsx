"use client";

import type { RiskAssessmentData, SourceBreakdown } from "@/lib/api";

const LEVEL_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
  Normal: { bg: "bg-green-500/10", text: "text-green-400", bar: "bg-green-500" },
  Elevated: { bg: "bg-amber-500/10", text: "text-amber-400", bar: "bg-amber-500" },
  Critical: { bg: "bg-red-500/10", text: "text-red-400", bar: "bg-red-500" },
};

const COMPONENT_LABELS: Record<string, string> = {
  event_severity: "Event Severity",
  fire_density: "Fire Activity",
  media_spike: "Media Coverage",
  confidence: "Data Confidence",
};

interface RiskScoreCardProps {
  riskAssessment: RiskAssessmentData;
  sourceBreakdown?: SourceBreakdown[];
  recommendations?: string[];
  overallConfidence?: number;
}

export default function RiskScoreCard({
  riskAssessment,
  sourceBreakdown,
  recommendations,
  overallConfidence,
}: RiskScoreCardProps) {
  const levelStyle = LEVEL_COLORS[riskAssessment.risk_level] || LEVEL_COLORS.Normal;

  return (
    <div className={`rounded-lg border border-gray-800 ${levelStyle.bg} p-3 space-y-3`}>
      {/* Score header */}
      <div className="flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <span className={`text-2xl font-bold tabular-nums ${levelStyle.text}`}>
            {riskAssessment.risk_score.toFixed(1)}
          </span>
          <span className="text-gray-500 text-xs">/5</span>
          <span
            className={`text-xs font-semibold px-2 py-0.5 rounded-full ${levelStyle.bg} ${levelStyle.text} border border-current/20`}
          >
            {riskAssessment.risk_level.toUpperCase()}
          </span>
        </div>
        {overallConfidence != null && (
          <span className="text-xs text-gray-500">
            Confidence: {(overallConfidence * 100).toFixed(0)}%
          </span>
        )}
      </div>

      {/* Component bars */}
      {riskAssessment.components && (
        <div className="space-y-1.5">
          {Object.entries(riskAssessment.components).map(([key, value]) => (
            <div key={key} className="flex items-center gap-2 text-xs">
              <span className="text-gray-500 w-28 flex-shrink-0">
                {COMPONENT_LABELS[key] || key}
              </span>
              <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${levelStyle.bar} transition-all`}
                  style={{ width: `${(value / 5) * 100}%` }}
                />
              </div>
              <span className="text-gray-600 w-6 text-right tabular-nums">
                {value.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Source breakdown */}
      {sourceBreakdown && sourceBreakdown.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-400">
            Source breakdown ({sourceBreakdown.length} sources)
          </summary>
          <div className="mt-1.5 space-y-0.5">
            {sourceBreakdown.map((src) => (
              <div
                key={src.source}
                className="flex items-center gap-2 text-xs text-gray-400"
              >
                <span className="w-20 flex-shrink-0 font-medium">
                  {src.source}
                </span>
                <span className="text-gray-600">
                  rel: {src.reliability.toFixed(2)}
                </span>
                <span className="text-gray-600">
                  fresh: {src.freshness.toFixed(2)}
                </span>
                <span className="text-gray-600">
                  {src.items_count} items
                </span>
              </div>
            ))}
          </div>
        </details>
      )}

      {/* Recommendations */}
      {recommendations && recommendations.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-gray-500 font-medium">Recommendations</div>
          <ul className="space-y-0.5">
            {recommendations.map((rec, i) => (
              <li key={i} className="text-xs text-gray-400 flex gap-1.5">
                <span className="text-gray-600 flex-shrink-0">-</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Explanation */}
      {riskAssessment.explanation && (
        <p className="text-xs text-gray-500 italic">
          {riskAssessment.explanation}
        </p>
      )}
    </div>
  );
}
