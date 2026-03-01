"use client";

import type { TimelineStep } from "@/lib/api";

const AGENT_CONFIG: Record<
  string,
  { icon: string; color: string; bgColor: string }
> = {
  manager: {
    icon: "\u{1F9E0}",
    color: "text-purple-400",
    bgColor: "bg-purple-500/10",
  },
  EmergencyMonitor: {
    icon: "\u{1F30D}",
    color: "text-red-400",
    bgColor: "bg-red-500/10",
  },
  SocialNewsAgent: {
    icon: "\u{1F4F0}",
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
  },
  FireMonitorAgent: {
    icon: "\u{1F525}",
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
  },
  AnalysisAgent: {
    icon: "\u{1F4CA}",
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
  },
};

function getConfig(agent: string) {
  return (
    AGENT_CONFIG[agent] || {
      icon: "\u{2699}\u{FE0F}",
      color: "text-gray-400",
      bgColor: "bg-gray-500/10",
    }
  );
}

function formatElapsed(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

interface AgentTimelineProps {
  steps: TimelineStep[];
  isLive: boolean;
  collapsed?: boolean;
}

export default function AgentTimeline({
  steps,
  isLive,
  collapsed = false,
}: AgentTimelineProps) {
  if (steps.length === 0) return null;

  const content = (
    <div className="space-y-1">
      {steps.map((step, i) => {
        const config = getConfig(step.agent);
        const isLatest = isLive && i === steps.length - 1;

        return (
          <div
            key={step.step}
            className={`flex items-start gap-2 px-2 py-1 rounded text-xs ${config.bgColor} ${
              isLatest ? "ring-1 ring-white/10" : ""
            }`}
          >
            <span className="flex-shrink-0 w-5 text-center">{config.icon}</span>
            <span className={`font-medium flex-shrink-0 w-24 ${config.color}`}>
              {step.agent === "manager" ? "Manager" : step.agent}
            </span>
            <span className="text-gray-400 flex-1 truncate">{step.message}</span>
            <span className="text-gray-600 flex-shrink-0 tabular-nums w-12 text-right">
              {formatElapsed(step.elapsed_ms)}
            </span>
            {isLatest && (
              <span className="flex-shrink-0 w-2 h-2 rounded-full bg-green-500 animate-pulse mt-1" />
            )}
          </div>
        );
      })}
    </div>
  );

  if (collapsed) {
    return (
      <details className="group">
        <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-400 flex items-center gap-1 py-1">
          <svg
            className="w-3 h-3 transition-transform group-open:rotate-90"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
          Agent reasoning ({steps.length} steps,{" "}
          {formatElapsed(steps[steps.length - 1]?.elapsed_ms || 0)} total)
        </summary>
        <div className="mt-1">{content}</div>
      </details>
    );
  }

  return (
    <div className="border border-gray-800 rounded-lg p-2 bg-gray-900/50">
      <div className="text-xs text-gray-500 mb-1.5 font-medium">
        Agent Reasoning Timeline
      </div>
      {content}
    </div>
  );
}
