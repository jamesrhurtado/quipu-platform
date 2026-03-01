"use client";

const AGENT_INFO: Record<string, { label: string; color: string }> = {
  manager: { label: "Manager", color: "bg-purple-500" },
  EmergencyMonitor: { label: "Emergency", color: "bg-red-500" },
  SocialNewsAgent: { label: "News & Social", color: "bg-blue-500" },
  FireMonitorAgent: { label: "Fire Monitor", color: "bg-green-500" },
  AnalysisAgent: { label: "Analysis", color: "bg-amber-500" },
};

interface AgentStatusProps {
  agent: string;
}

export default function AgentStatus({ agent }: AgentStatusProps) {
  const info = AGENT_INFO[agent] || { label: agent, color: "bg-gray-500" };

  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-2 h-2 rounded-full ${info.color} animate-pulse`} />
      <span className="text-xs text-gray-400">{info.label}</span>
    </div>
  );
}
