"use client";

import { FormEvent, useCallback, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import AgentStatus from "./AgentStatus";
import AgentTimeline from "./AgentTimeline";
import RiskScoreCard from "./RiskScoreCard";
import {
  AgentChunk,
  MapFocusInstruction,
  RiskAssessmentData,
  SourceBreakdown,
  TimelineStep,
  streamQuery,
} from "@/lib/api";

interface Message {
  role: "user" | "assistant" | "agent";
  content: string;
  agent?: string;
  timeline?: TimelineStep[];
  riskAssessment?: RiskAssessmentData;
  sourceBreakdown?: SourceBreakdown[];
  recommendations?: string[];
  overallConfidence?: number;
}

interface ChatInterfaceProps {
  onMapFocus?: (focus: MapFocusInstruction) => void;
}

export default function ChatInterface({ onMapFocus }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [timelineSteps, setTimelineSteps] = useState<TimelineStep[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || streaming) return;

    setInput("");
    setStreaming(true);
    setTimelineSteps([]);
    setMessages((prev) => [...prev, { role: "user", content: query }]);

    try {
      let finalAnswer = "";
      let riskAssessment: RiskAssessmentData | undefined;
      let sourceBreakdown: SourceBreakdown[] | undefined;
      let recommendations: string[] | undefined;
      let overallConfidence: number | undefined;
      let mapFocus: MapFocusInstruction | undefined;
      const collectedTimeline: TimelineStep[] = [];
      const agentMessages: Message[] = [];

      for await (const chunk of streamQuery(query)) {
        switch (chunk.type) {
          case "status":
            setActiveAgent(chunk.agent || null);
            break;

          case "classification":
            // Classification is informational — already reflected in timeline
            break;

          case "timeline_step":
            if (
              chunk.step != null &&
              chunk.agent &&
              chunk.action &&
              chunk.message &&
              chunk.elapsed_ms != null
            ) {
              const step: TimelineStep = {
                step: chunk.step,
                agent: chunk.agent,
                action: chunk.action,
                message: chunk.message,
                elapsed_ms: chunk.elapsed_ms,
              };
              collectedTimeline.push(step);
              setTimelineSteps([...collectedTimeline]);
            }
            break;

          case "agent_response":
            setActiveAgent(chunk.agent || null);
            agentMessages.push({
              role: "agent",
              content: chunk.content || "",
              agent: chunk.agent,
            });
            break;

          case "final_answer":
            finalAnswer = chunk.content || "";
            riskAssessment = chunk.risk_assessment;
            sourceBreakdown = chunk.source_breakdown;
            recommendations = chunk.recommendations;
            overallConfidence = chunk.overall_confidence;
            mapFocus = chunk.map_focus;
            break;

          case "error":
            finalAnswer = `Error: ${chunk.message}`;
            break;

          case "done":
            break;
        }
        scrollToBottom();
      }

      // Apply map focus if provided
      if (mapFocus && onMapFocus) {
        onMapFocus(mapFocus);
      }

      setMessages((prev) => [
        ...prev,
        ...agentMessages,
        {
          role: "assistant",
          content: finalAnswer,
          timeline: collectedTimeline.length > 0 ? collectedTimeline : undefined,
          riskAssessment,
          sourceBreakdown,
          recommendations,
          overallConfidence,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Connection error: ${err instanceof Error ? err.message : "Unknown error"}`,
        },
      ]);
    } finally {
      setStreaming(false);
      setActiveAgent(null);
      setTimelineSteps([]);
      scrollToBottom();
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-gray-800 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-300">
          Ask Sentinel
        </h2>
        {activeAgent && <AgentStatus agent={activeAgent} />}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-600 text-sm mt-4">
            <p>Ask about disasters in Latin America</p>
            <div className="mt-3 space-y-1 text-xs">
              <p className="text-gray-700">
                &quot;What&apos;s happening in Peru right now?&quot;
              </p>
              <p className="text-gray-700">
                &quot;Are there active fires in the Amazon?&quot;
              </p>
              <p className="text-gray-700">
                &quot;Generate a situation report for Central America&quot;
              </p>
            </div>
          </div>
        )}

        {messages.filter((msg) => !(msg.role === "agent" && !msg.content.trim())).map((msg, i) => (
          <div
            key={i}
            className={`${
              msg.role === "user"
                ? "ml-8"
                : msg.role === "agent"
                ? "mr-8 opacity-60"
                : "mr-8"
            }`}
          >
            {msg.role === "agent" && (
              <div className="text-xs text-gray-500 mb-1">
                {msg.agent}
              </div>
            )}
            <div
              className={`rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-sentinel-800 text-gray-100"
                  : msg.role === "agent"
                  ? "bg-gray-800/50 text-gray-400 text-xs border border-gray-800"
                  : "bg-gray-800 text-gray-200"
              }`}
            >
              {msg.role === "assistant" ? (
                <>
                  {msg.timeline && (
                    <div className="mb-2">
                      <AgentTimeline
                        steps={msg.timeline}
                        isLive={false}
                        collapsed
                      />
                    </div>
                  )}
                  <ReactMarkdown
                    className="prose prose-invert prose-sm max-w-none
                      prose-p:my-1 prose-li:my-0.5 prose-ul:my-1 prose-ol:my-1
                      prose-headings:my-2 prose-headings:text-gray-200"
                  >
                    {msg.content}
                  </ReactMarkdown>
                  {msg.riskAssessment && (
                    <div className="mt-2">
                      <RiskScoreCard
                        riskAssessment={msg.riskAssessment}
                        sourceBreakdown={msg.sourceBreakdown}
                        recommendations={msg.recommendations}
                        overallConfidence={msg.overallConfidence}
                      />
                    </div>
                  )}
                </>
              ) : msg.role === "agent" ? (
                <details>
                  <summary className="cursor-pointer">
                    {msg.content.slice(0, 80)}
                    {msg.content.length > 80 ? "..." : ""}
                  </summary>
                  <div className="mt-1 whitespace-pre-wrap">
                    {msg.content}
                  </div>
                </details>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {/* Live timeline during streaming */}
        {streaming && timelineSteps.length > 0 && (
          <div className="mr-8">
            <AgentTimeline steps={timelineSteps} isLive />
          </div>
        )}

        {streaming && (
          <div className="mr-8">
            <div className="bg-gray-800 rounded-lg px-3 py-2 text-sm text-gray-400">
              <span className="inline-flex gap-1">
                <span className="animate-bounce" style={{ animationDelay: "0ms" }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: "150ms" }}>.</span>
                <span className="animate-bounce" style={{ animationDelay: "300ms" }}>.</span>
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="px-4 py-3 border-t border-gray-800"
      >
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about disasters..."
            disabled={streaming}
            className="flex-1 bg-gray-800 text-gray-200 rounded-lg px-3 py-2 text-sm
              placeholder:text-gray-600 focus:outline-none focus:ring-1
              focus:ring-sentinel-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={streaming || !input.trim()}
            className="bg-sentinel-600 hover:bg-sentinel-700 text-white rounded-lg px-4 py-2
              text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
