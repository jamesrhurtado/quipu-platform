const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Event {
  id: string;
  external_id: string;
  source: string;
  event_type: string;
  title: string;
  description: string | null;
  severity: number;
  magnitude: number | null;
  lat: number;
  lon: number;
  started_at: string | null;
  updated_at: string | null;
  created_at: string | null;
  is_active: boolean;
}

export interface EventsResponse {
  events: Event[];
  count: number;
}

export interface TimelineStep {
  step: number;
  agent: string;
  action: string;
  message: string;
  content?: string;
  reasoning?: string;
  elapsed_ms: number;
}

export interface RiskAssessmentData {
  risk_score: number;
  risk_level: string;
  components: Record<string, number>;
  explanation: string;
}

export interface SourceBreakdown {
  source: string;
  reliability: number;
  freshness: number;
  items_count: number;
}

export interface MapFocusInstruction {
  center_lat: number;
  center_lon: number;
  zoom: number;
  highlight_region?: string;
}

export interface AgentChunk {
  type:
    | "status"
    | "agent_response"
    | "final_answer"
    | "error"
    | "done"
    | "timeline_step"
    | "classification";
  agent?: string;
  message?: string;
  content?: string;
  // timeline_step fields
  step?: number;
  action?: string;
  elapsed_ms?: number;
  // classification fields
  agents?: string[];
  reasoning?: string;
  // final_answer structured fields
  risk_assessment?: RiskAssessmentData;
  source_breakdown?: SourceBreakdown[];
  map_focus?: MapFocusInstruction;
  recommendations?: string[];
  overall_confidence?: number;
}

export async function fetchEvents(params?: {
  hours?: number;
  min_severity?: number;
  event_type?: string;
}): Promise<EventsResponse> {
  const searchParams = new URLSearchParams();
  // Default to Latin America bbox
  searchParams.set("min_lat", "-56");
  searchParams.set("max_lat", "33");
  searchParams.set("min_lon", "-118");
  searchParams.set("max_lon", "-34");
  if (params?.hours) searchParams.set("hours", String(params.hours));
  if (params?.min_severity)
    searchParams.set("min_severity", String(params.min_severity));
  if (params?.event_type) searchParams.set("event_type", params.event_type);

  const resp = await fetch(`${API_BASE}/api/events?${searchParams}`);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function* streamQuery(
  query: string
): AsyncGenerator<AgentChunk, void, unknown> {
  const resp = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  if (!resp.ok) throw new Error(`Query failed: ${resp.status}`);
  if (!resp.body) throw new Error("No response body");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          yield data as AgentChunk;
        } catch {
          // ignore malformed JSON
        }
      }
    }
  }
}

export function createSSEConnection(
  onEvent: (event: string, data: unknown) => void,
  onError?: () => void
): EventSource {
  const es = new EventSource(`${API_BASE}/api/stream`);

  es.addEventListener("connected", () => {
    onEvent("connected", { status: "ok" });
  });

  es.addEventListener("new_event", (e) => {
    try {
      onEvent("new_event", JSON.parse(e.data));
    } catch {}
  });

  es.addEventListener("new_events_batch", (e) => {
    try {
      onEvent("new_events_batch", JSON.parse(e.data));
    } catch {}
  });

  es.addEventListener("poll_complete", (e) => {
    try {
      onEvent("poll_complete", JSON.parse(e.data));
    } catch {}
  });

  es.onerror = () => {
    onError?.();
  };

  return es;
}
