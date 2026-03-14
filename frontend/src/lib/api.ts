const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Auth token getter — set by AuthProvider when auth is enabled
let _getAuthToken: (() => Promise<string | null>) | null = null;

export function setAuthTokenGetter(getter: () => Promise<string | null>) {
  _getAuthToken = getter;
}

async function authHeaders(): Promise<Record<string, string>> {
  if (!_getAuthToken) return {};
  const token = await _getAuthToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export interface UserInfo {
  user: {
    id: string;
    email: string;
    display_name: string | null;
    role: string | null;
  };
  organization: {
    id: string;
    name: string;
    slug: string;
    municipality: string;
    department: string | null;
    map_center_lat: number;
    map_center_lon: number;
    map_zoom: number;
    onboarding_completed: boolean;
  } | null;
}

export async function fetchMe(): Promise<UserInfo> {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/auth/me`, { headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

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

// Phase 1: Risk driver transparency
export interface RiskDriver {
  component: string;
  label: string;
  value: number;
  reason: string;
}

export interface ComponentAnalysis {
  label: string;
  value: number;
  weight: number;
  weighted_contribution: number;
  interpretation: string;
}

// Phase 2: Trend data
export interface TrendData {
  trend: string;
  pct_change: number;
  data_points: number;
  first_score?: number;
  last_score?: number;
  slope_per_hour?: number;
  history?: { risk_score: number; risk_level: string; created_at: string }[];
}

// Phase 3: Alert data
export interface AlertData {
  id: string;
  region: string;
  alert_level: "elevated" | "high" | "critical";
  risk_score: number;
  risk_level: string;
  explanation: string;
  drivers: RiskDriver[];
  actions_taken: { type: string; target: string; label: string; status: string; message: string }[];
  acknowledged: boolean;
  created_at: string;
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
  // Phase 1: risk drivers
  risk_drivers?: RiskDriver[];
  // Phase 2: trend
  trend?: TrendData;
}

export async function fetchEvents(params?: {
  hours?: number;
  min_severity?: number;
  event_type?: string;
}): Promise<EventsResponse> {
  const searchParams = new URLSearchParams();
  // No longer send hardcoded bbox — backend defaults to org's bbox when multi-tenant
  if (params?.hours) searchParams.set("hours", String(params.hours));
  if (params?.min_severity)
    searchParams.set("min_severity", String(params.min_severity));
  if (params?.event_type) searchParams.set("event_type", params.event_type);

  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/events?${searchParams}`, { headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

// --- Onboarding / Municipality APIs ---

export interface Municipality {
  name: string;
  department: string;
  lat: number;
  lon: number;
  bbox: { min_lat: number; max_lat: number; min_lon: number; max_lon: number };
  distance_km?: number;
}

export async function fetchMunicipalities(q?: string): Promise<{ municipalities: Municipality[]; count: number }> {
  const headers = await authHeaders();
  const params = q ? `?q=${encodeURIComponent(q)}` : "";
  const resp = await fetch(`${API_BASE}/api/municipalities${params}`, { headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function fetchNearbyMunicipalities(name: string, radiusKm = 100): Promise<{
  municipality: Municipality;
  nearby: Municipality[];
}> {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/municipalities/${encodeURIComponent(name)}/nearby?radius_km=${radiusKm}`, { headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function createOrganization(municipalityName: string, additionalZones: string[] = []) {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/onboarding/organization`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ municipality_name: municipalityName, additional_zones: additionalZones }),
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function updateNotifications(config: {
  teams_webhook_url?: string;
  teams_enabled: boolean;
  bluesky_handle?: string;
  bluesky_app_password?: string;
  bluesky_enabled: boolean;
}) {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/onboarding/notifications`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(config),
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function updateContacts(contacts: {
  name: string;
  role?: string;
  phone?: string;
  email?: string;
  notify_on_level: string[];
}[]) {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/onboarding/contacts`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ contacts }),
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function completeOnboarding() {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/onboarding/complete`, {
    method: "POST",
    headers: { ...headers },
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function testTeams() {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/onboarding/test-teams`, {
    method: "POST",
    headers: { ...headers },
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function testBluesky() {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/onboarding/test-bluesky`, {
    method: "POST",
    headers: { ...headers },
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

// --- Settings APIs ---

export interface OrgSettings {
  organization: {
    id: string;
    name: string;
    slug: string;
    municipality: string;
    department: string | null;
    country: string;
    map_center_lat: number;
    map_center_lon: number;
    map_zoom: number;
    created_at: string;
  };
  notifications: {
    teams_webhook_url: string | null;
    teams_enabled: boolean;
    bluesky_handle: string | null;
    bluesky_enabled: boolean;
  };
  monitored_zones: {
    id: string;
    name: string;
    is_primary: boolean;
    bbox: { min_lat: number; max_lat: number; min_lon: number; max_lon: number };
  }[];
}

export async function fetchSettings(): Promise<OrgSettings> {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/settings/organization`, { headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function updateSettingsNotifications(config: {
  teams_webhook_url?: string | null;
  teams_enabled: boolean;
  bluesky_handle?: string | null;
  bluesky_app_password?: string;
  bluesky_enabled: boolean;
}) {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/settings/notifications`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(config),
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function testSettingsTeams() {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/settings/test-teams`, { method: "POST", headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function testSettingsBluesky() {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/settings/test-bluesky`, { method: "POST", headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export interface EmergencyContact {
  id: string;
  name: string;
  role: string | null;
  phone: string | null;
  email: string | null;
  notify_on_level: string[];
}

export async function fetchContacts(): Promise<{ contacts: EmergencyContact[]; count: number }> {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/settings/contacts`, { headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function addContact(contact: {
  name: string;
  role?: string;
  phone?: string;
  email?: string;
  notify_on_level: string[];
}) {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/settings/contacts`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(contact),
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function deleteContact(id: string) {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/settings/contacts/${id}`, {
    method: "DELETE",
    headers,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function deleteOrganization() {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/settings/organization`, {
    method: "DELETE",
    headers,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function fetchAlerts(params?: {
  acknowledged?: boolean;
  limit?: number;
}): Promise<{ alerts: AlertData[]; count: number }> {
  const searchParams = new URLSearchParams();
  if (params?.acknowledged !== undefined) searchParams.set("acknowledged", String(params.acknowledged));
  if (params?.limit) searchParams.set("limit", String(params.limit));
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/alerts?${searchParams}`, { headers });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function acknowledgeAlert(id: string) {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/alerts/${id}/acknowledge`, {
    method: "PATCH",
    headers,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

// --- Public Status API (no auth) ---

export interface PublicStatus {
  municipality: string;
  department: string | null;
  name: string;
  location: { lat: number; lon: number };
  risk: {
    score: number | null;
    level: string;
    explanation: string | null;
    updated_at: string | null;
  };
  active_alerts: number;
  recent_alerts: {
    alert_level: string;
    risk_score: number;
    region: string;
    created_at: string;
  }[];
}

export async function fetchPublicStatus(slug: string): Promise<PublicStatus> {
  const resp = await fetch(`${API_BASE}/api/status/${encodeURIComponent(slug)}`);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export async function* streamQuery(
  query: string
): AsyncGenerator<AgentChunk, void, unknown> {
  const headers = await authHeaders();
  const resp = await fetch(`${API_BASE}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
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

export async function createSSEConnection(
  onEvent: (event: string, data: unknown) => void,
  onError?: () => void
): Promise<EventSource> {
  // Pass auth token as query param since EventSource doesn't support headers
  let url = `${API_BASE}/api/stream`;
  if (_getAuthToken) {
    const token = await _getAuthToken();
    if (token) {
      url += `?token=${encodeURIComponent(token)}`;
    }
  }
  const es = new EventSource(url);

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

  es.addEventListener("alert", (e) => {
    try {
      onEvent("alert", JSON.parse(e.data));
    } catch {}
  });

  es.onerror = () => {
    onError?.();
  };

  return es;
}
