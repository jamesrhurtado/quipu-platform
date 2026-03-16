# Quipu

**An AI-powered multi-tenant early warning platform where 7 specialized agents monitor earthquakes, fires, floods, and climate risks in real time — automatically alerting Peruvian municipalities through Microsoft Teams and Bluesky before disasters escalate.**

Quipu — named after the Inca knotted-string recording system — is built with the Microsoft Agent Framework and Azure OpenAI. Seven specialized agents collaborate through MagenticOne orchestration to monitor disaster signals from 8+ live sources — USGS, GDACS, NASA EONET, NASA FIRMS, GDELT, ReliefWeb, Bluesky, and Open-Meteo — and alert communities before crises escalate. Each municipality gets its own dashboard, monitoring zones, notification channels, and a shareable public risk page for citizens.

Ask a question in natural language. Quipu figures out which agents to activate, queries the right APIs, scores source reliability, computes a composite risk assessment, detects rainfall anomalies, and sends real alerts to your Teams channel — all in seconds.

![Python](https://img.shields.io/badge/python-3.13-blue)
![Next.js](https://img.shields.io/badge/next.js-14-black)
![Agent Framework](https://img.shields.io/badge/agent--framework-1.0rc3-purple)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Example

**1. Onboard a municipality** — Sign in with Microsoft, select your city (e.g. Arequipa), and nearby monitoring zones within 100 km are automatically discovered. Configure notification channels (Microsoft Teams, Bluesky) and finish setup in minutes.

**2. Monitor your dashboard** — The dashboard is scoped to your municipality. See earthquakes, fires, and disaster alerts within your monitoring zone updating in real time on an interactive map.

**3. Ask a question** — Type `"What's the current situation in Arequipa?"` and seven agents investigate in parallel using MagenticOne orchestration:

```
Manager    -> Selected all agents for broad situation query              0.2s
Emergency  -> Found M4.1 earthquake, 2 GDACS alerts in zone             1.8s
Weather    -> Rainfall anomaly +120% above historical average            2.4s
News       -> 12 articles from GDELT, 3 ReliefWeb reports               2.6s
Analysis   -> Compound risk score: ELEVATED (3.8/5)                      3.1s
Manager    -> Synthesizing intelligence report                           4.0s
```

**4. Get alerted automatically** — When risk crosses a threshold, alerts arrive as Adaptive Cards in Microsoft Teams with risk breakdowns and links to the dashboard. A background poller runs every five minutes, computing risk scores with zero AI cost for 24/7 compound risk detection.

**5. Share with citizens** — Each municipality also has a shareable public risk page that citizens can access directly.

---

## Why Quipu Exists

Disasters rarely happen alone. Peru faces over 5,000 natural hazard events annually — earthquakes, floods, landslides, and wildfires — yet most of its 1,800+ municipalities lack any monitoring infrastructure. Emergency coordinators rely on WhatsApp rumors and national news, often learning about compound risks (like earthquakes during heavy rainfall triggering landslides) hours after the danger window closes.

When a 7.2 earthquake hits near Cusco during heavy rainfall season, information fractures across dozens of sources: USGS reports the seismology, GDACS estimates impact, weather data shows abnormal precipitation, NASA detects landslide risk, news outlets report casualties at different speeds, and social media fills with unverified claims. Emergency coordinators must manually piece this together under time pressure.

Quipu automates that synthesis. It treats each data domain as a specialist agent, orchestrates them dynamically based on the query, computes compound risks (earthquake + heavy rainfall = landslide danger), and delivers alerts directly to Microsoft Teams and Bluesky — not just raw data, but assessed, scored, and actionable.

---

## Architecture

> 📐 **Interactive architecture diagram**: [quipu-guardian-angel.lovable.app](https://preview--quipu-guardian-angel.lovable.app/)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                         │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Leaflet  │  │ Agent      │  │ Risk     │  │ Chat         │  │
│  │ Map      │  │ Timeline   │  │ ScoreCard│  │ Interface    │  │
│  └──────────┘  └────────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │ SSE + REST
┌─────────────────────────┴───────────────────────────────────────┐
│                       FastAPI Backend                            │
│                                                                  │
│  ┌─────────────────── Magentic Orchestration ──────────────────┐ │
│  │                                                              │ │
│  │  Query Classifier ──→ Dynamic Agent Selection                │ │
│  │       │                                                      │ │
│  │       ▼                                                      │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │ │
│  │  │Emergency │ │Social &  │ │Fire      │ │Analysis      │   │ │
│  │  │Monitor   │ │News      │ │Monitor   │ │Agent         │   │ │
│  │  │• USGS    │ │• GDELT   │ │• NASA    │ │• PostGIS     │   │ │
│  │  │• GDACS   │ │• Bluesky │ │  FIRMS   │ │• Risk Engine │   │ │
│  │  │• EONET   │ │• Relief  │ │          │ │• Sitreps     │   │ │
│  │  │• PostGIS │ │  Web     │ │          │ │• Trends      │   │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │ │
│  │  ┌──────────┐ ┌──────────────────────────────────────────┐  │ │
│  │  │Weather   │ │Notification Agent                        │  │ │
│  │  │Agent     │ │• Microsoft Teams (Adaptive Cards)        │  │ │
│  │  │• Open-   │ │• Bluesky (bilingual public advisories)   │  │ │
│  │  │  Meteo   │ │• Notification audit trail                │  │ │
│  │  └──────────┘ └──────────────────────────────────────────┘  │ │
│  │       │              │           │              │            │ │
│  │       └──────────────┴───────────┴──────────────┘            │ │
│  │                    Source Scoring Layer                       │ │
│  │              (reliability × freshness weights)               │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Background   │  │ SSE Manager  │  │ Risk Escalation       │  │
│  │ Poller (5m)  │  │ (real-time)  │  │ Engine + Auto-Risk    │  │
│  │ + Auto-Risk  │  │              │  │ + Teams/Bluesky       │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                │  PostgreSQL +     │
                │  PostGIS          │
                └───────────────────┘
```

### Three-Tier Design

**Tier 1 — Background Poller + Auto-Risk (no LLM, runs continuously)**
A lightweight loop polls USGS, GDACS, NASA EONET, and FIRMS every 5 minutes, normalizes events, and upserts them into PostGIS. After each poll cycle, an auto-risk step computes risk scores for all monitored regions (Peru, Cusco, Lima, Piura, Arequipa) — if any region crosses the alert threshold, real notifications fire to Teams and Bluesky automatically. Zero LLM cost.

**Tier 2 — Agent Orchestration (LLM, on-demand)**
When a user asks a question, the system activates. A keyword classifier determines which agents are relevant — a rainfall query activates only WeatherAgent + AnalysisAgent, skipping the others entirely. Selected agents run in parallel via MagenticOrchestration, each calling live APIs with their specialized tools. Results flow through a scoring layer that attaches reliability and freshness weights before the manager synthesizes everything.

**Tier 3 — Notification Delivery (on-demand or automatic)**
The NotificationAgent delivers alerts to Microsoft Teams (Adaptive Cards) and Bluesky (bilingual public advisories). It can be triggered automatically by the risk engine or manually by the user ("send an alert to Teams"). All deliveries are logged to an audit trail.

---

## Agents

| # | Agent | Model | Tools | Role |
|---|-------|-------|-------|------|
| 1 | **Manager** | GPT-4o | — | Orchestrates specialists, synthesizes final report |
| 2 | **EmergencyMonitor** | GPT-4o-mini | `query_earthquakes`, `query_gdacs_alerts`, `query_eonet_events`, `query_cached_events` | Seismic/disaster alerts |
| 3 | **SocialNewsAgent** | GPT-4o-mini | `search_gdelt_news`, `monitor_bluesky`, `search_reliefweb` | News + social monitoring |
| 4 | **FireMonitorAgent** | GPT-4o-mini | `query_active_fires` | Satellite fire detection |
| 5 | **AnalysisAgent** | GPT-4o | `query_event_database`, `generate_situation_report`, `compute_risk_assessment`, `get_risk_trend` | Risk scoring + trends |
| 6 | **WeatherAgent** | GPT-4o-mini | `check_rainfall_anomaly` | Rainfall anomaly detection |
| 7 | **NotificationAgent** | GPT-4o-mini | `send_teams_alert`, `post_bluesky_alert`, `get_notification_history` | Teams + Bluesky delivery |

---

## Key Features

### Multi-Tenant Architecture
Each municipality gets:
- Scoped dashboard with map centered on their city and monitored zone boundaries
- Independent risk scoring per monitored zone
- Per-organization Teams webhook and Bluesky credentials (encrypted with Fernet)
- Emergency contact roster with alert level triggers
- Shareable public status page at `/status/{city-slug}` for citizens (no login required)

Onboarding takes minutes — select a city from 50 Peruvian municipalities and nearby monitoring zones within 100 km are automatically discovered.

### Dynamic Agent Selection
Queries are classified at intake. `"What's the rainfall in Cusco?"` activates WeatherAgent + AnalysisAgent. `"Send an alert to Teams"` activates NotificationAgent. `"What's happening in Peru?"` activates all agents. The reasoning is transparent — every query produces a classification event explaining why specific agents were chosen.

### Rainfall Anomaly Detection
The WeatherAgent compares recent precipitation against a 5-year historical average using Open-Meteo's free APIs. When rainfall exceeds 80% above normal, it flags landslide risk — especially dangerous when combined with seismic activity.

### Real Notification Delivery
Alerts are delivered to real channels, not just simulated:
- **Microsoft Teams**: Adaptive Cards with color-coded headers, risk drivers, and a "View Dashboard" button
- **Bluesky**: Bilingual (Spanish/English) public advisories via the AT Protocol

Each channel can be independently enabled or disabled via environment variables.

### Automatic Risk Monitoring
Every 5-minute poll cycle triggers an automatic risk assessment for monitored regions. When a region crosses the alert threshold (risk score >= 3.0), notifications fire automatically — no human trigger required.

### Probabilistic Source Scoring
Every tool result carries two scores:
- **Reliability** — static weight per source (USGS: 1.0, GDACS: 0.9, GDELT: 0.6, Bluesky: 0.4, Open-Meteo: 0.8)
- **Freshness** — linear decay from 1.0 (now) to 0.0 (7 days old), computed from actual data timestamps

### Compound Risk Detection
The core innovation is correlating signals across domains. No single data source tells you that a M4.9 earthquake happened 28km from your city during a period of below-normal rainfall, while 9 active fires are detected in the region and 5 news articles report seismic activity. Quipu's agents correlate these signals — determining that dry conditions reduce landslide risk from the earthquake but increase fire spread vulnerability — producing actionable intelligence that no individual API can provide.

### Composite Risk Engine
A weighted formula combines four normalized components:

| Component | Weight | Source |
|-----------|--------|--------|
| Event severity | 35% | Max severity from disaster events (1-5) |
| Fire density | 20% | Active fire count vs baseline |
| Media spike | 20% | Article count vs baseline |
| Data confidence | 25% | Average (reliability x freshness) |

Output: **Normal** (1-2.9), **Elevated** (3-3.9), or **Critical** (4-5). Persisted to database for trend analysis.

### Agent Reasoning Timeline
Every orchestration step is timed and streamed to the frontend as it happens:
```
Manager    -> Selected EmergencyMonitor + WeatherAgent + AnalysisAgent    0.2s
Emergency  -> Found M4.1 earthquake 80km from Cusco                      1.8s
Weather    -> Rainfall anomaly +120% above historical average            2.4s
Analysis   -> Risk score computed: CRITICAL (4.6/5)                      3.1s
Manager    -> Synthesizing intelligence report                           4.0s
```

---

## Data Sources

| Source | Data | Auth | Latency |
|--------|------|------|---------|
| [USGS Earthquake API](https://earthquake.usgs.gov/fdsnws/event/1/) | Earthquakes worldwide | None | Real-time |
| [GDACS](https://www.gdacs.org/) | Multi-hazard alerts (EQ, TC, FL, VO, WF, DR) | None | ~30 min |
| [NASA EONET](https://eonet.gsfc.nasa.gov/) | Curated natural events | Free key | Near-real-time |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | Active fire detections (VIIRS/MODIS) | Free MAP_KEY | ~1 hour |
| [GDELT DOC 2.0](https://www.gdeltproject.org/) | Global news monitoring (65+ languages) | None | 15 min |
| [ReliefWeb](https://reliefweb.int/) | UN OCHA humanitarian reports | Free appname | Daily |
| [Bluesky](https://bsky.app/) | Social media disaster mentions | None | Real-time |
| [Open-Meteo](https://open-meteo.com/) | Precipitation data + 5-year historical averages | None | Daily |

---

## Quick Start

### Prerequisites

- Python 3.13+
- Node.js 18+
- Docker (for PostgreSQL + PostGIS)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/sentinel-agent.git
cd sentinel-agent
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Required — Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key

# Optional — Data sources
NASA_FIRMS_MAP_KEY=your-firms-key    # Get free at https://firms.modaps.eosdis.nasa.gov/api/area/

# Optional — Notification channels (see Configuration section)
TEAMS_WEBHOOK_URL=https://your-org.webhook.office.com/...
BLUESKY_HANDLE=your-handle.bsky.social
BLUESKY_APP_PASSWORD=your-app-password
```

### 2. Start the database

```bash
docker-compose up db
```

### 3. Start the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn main:app --reload
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**.

### 5. (Optional) Set up Teams webhook

1. Open Teams -> channel -> `...` -> **Manage channel** -> **Connectors**
2. Find **Incoming Webhook** -> **Configure** -> name it `Quipu Alerts` -> **Create**
3. Copy the URL -> add to `.env`: `TEAMS_WEBHOOK_URL=https://...`

If connectors are disabled, use **Power Automate**: trigger "When a HTTP request is received" -> action "Post message in channel" -> use the HTTP URL.

---

## Configuration

### Core Settings

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Yes | Azure OpenAI API key |
| `DATABASE_URL` | No | PostgreSQL connection string (default: `postgresql://sentinel:sentinel@localhost:5432/sentinel`) |
| `POLL_INTERVAL_SECONDS` | No | Background poll frequency in seconds (default: `300`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

### Data Source Keys

| Variable | Required | Description |
|----------|----------|-------------|
| `NASA_FIRMS_MAP_KEY` | No | Enables fire detection (free at [FIRMS](https://firms.modaps.eosdis.nasa.gov/api/area/)) |
| `NASA_API_KEY` | No | NASA API key (defaults to `DEMO_KEY`) |
| `BLUESKY_ENABLED` | No | Set `true` to enable real-time social media feed (default: `false`) |

### Notification Channels

Each notification channel can be independently toggled on/off. This lets you use Teams without Bluesky, Bluesky without Teams, both, or neither.

| Variable | Default | Description |
|----------|---------|-------------|
| `TEAMS_ENABLED` | `true` | Master switch for Teams notifications. Set `false` to disable all Teams alerts even if webhook URL is configured. |
| `TEAMS_WEBHOOK_URL` | `""` | Teams Incoming Webhook URL. When empty, Teams alerts are simulated. |
| `BLUESKY_NOTIFICATIONS_ENABLED` | `true` | Master switch for Bluesky alert posts. Set `false` to disable all Bluesky notifications. |
| `BLUESKY_HANDLE` | `""` | Bluesky handle (e.g., `quipu.bsky.social`). When empty, Bluesky alerts are simulated. |
| `BLUESKY_APP_PASSWORD` | `""` | Bluesky app password (generate at bsky.app Settings -> App Passwords). |
| `DASHBOARD_URL` | `http://localhost:3000` | URL included in Teams Adaptive Card "View Dashboard" button. |

**Examples:**

```env
# Teams only (no Bluesky posts)
TEAMS_ENABLED=true
TEAMS_WEBHOOK_URL=https://your-org.webhook.office.com/...
BLUESKY_NOTIFICATIONS_ENABLED=false

# Bluesky only (no Teams)
TEAMS_ENABLED=false
BLUESKY_NOTIFICATIONS_ENABLED=true
BLUESKY_HANDLE=quipu.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# Both channels active
TEAMS_ENABLED=true
TEAMS_WEBHOOK_URL=https://your-org.webhook.office.com/...
BLUESKY_NOTIFICATIONS_ENABLED=true
BLUESKY_HANDLE=quipu.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

# All notifications disabled (simulation only)
TEAMS_ENABLED=false
BLUESKY_NOTIFICATIONS_ENABLED=false
```

---

## Project Structure

```
sentinel-agent/
├── backend/
│   ├── agents/
│   │   ├── classifier.py        # Query -> agent routing
│   │   ├── definitions.py       # Orchestration, timeline, structured output
│   │   ├── instructions.py      # Agent system prompts (7 agents)
│   │   ├── risk_engine.py       # Composite risk scoring
│   │   ├── scoring.py           # Source reliability + freshness
│   │   └── tools/
│   │       ├── emergency.py     # USGS, GDACS, EONET, PostGIS
│   │       ├── social.py        # GDELT, Bluesky, ReliefWeb
│   │       ├── satellite.py     # NASA FIRMS
│   │       ├── analysis.py      # DB analytics, sitreps, risk assessment
│   │       ├── weather.py       # Open-Meteo rainfall anomaly
│   │       └── notification.py  # Teams, Bluesky, notification history
│   ├── api/routes/
│   │   ├── alerts.py            # GET/PATCH /api/alerts
│   │   ├── events.py            # GET /api/events
│   │   ├── query.py             # POST /api/query (SSE stream)
│   │   ├── risk.py              # GET /api/risk-assessments
│   │   └── stream.py            # SSE /api/stream (live events)
│   ├── services/
│   │   ├── poller.py            # Background data ingestion + auto-risk
│   │   ├── alert_engine.py      # Risk escalation + real notifications
│   │   ├── notifier.py          # Teams webhook + Bluesky AT Protocol
│   │   ├── bluesky_buffer.py    # Bluesky Jetstream consumer
│   │   ├── normalizer.py        # Raw -> normalized event mapping
│   │   └── sse_manager.py       # Server-sent events broadcaster
│   ├── sql/schema.sql           # PostGIS schema (events, alerts, notifications, ...)
│   ├── config.py
│   ├── db.py
│   └── main.py
├── frontend/
│   └── src/
│       ├── app/page.tsx         # Dashboard layout
│       ├── components/
│       │   ├── Map.tsx          # Leaflet + marker clusters
│       │   ├── ChatInterface.tsx# Agent chat with timeline + risk card
│       │   ├── AgentTimeline.tsx # Live orchestration timeline
│       │   ├── RiskScoreCard.tsx # Risk assessment visualization
│       │   ├── AlertBanner.tsx  # Alert banners with delivery status
│       │   ├── EventFeed.tsx    # Real-time event list
│       │   └── AgentStatus.tsx  # Agent activity indicator
│       ├── hooks/
│       │   ├── useEvents.ts     # Event polling hook
│       │   └── useSSE.ts        # SSE connection hook
│       └── lib/api.ts           # API client + types
└── docker-compose.yml
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/events` | Query cached events (supports bbox, severity, type filters) |
| `POST` | `/api/query` | Run agent query, returns SSE stream |
| `GET` | `/api/stream` | Live SSE feed of new events from poller |
| `GET` | `/api/risk-assessments` | Historical risk assessments (optional `?region=` filter) |
| `GET` | `/api/alerts` | Recent alerts with delivery status |
| `PATCH` | `/api/alerts/:id/acknowledge` | Acknowledge an alert |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) + Semantic Kernel (MagenticOne Orchestration) |
| LLM | Azure OpenAI GPT-4o + GPT-4o-mini via Azure AI Foundry |
| Authentication | Azure Entra ID (MSAL PKCE flow) |
| Backend | Python 3.13, FastAPI, asyncpg, httpx |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Map | Leaflet + leaflet.markercluster |
| Database | Azure Database for PostgreSQL + PostGIS 3.4 |
| Real-time | Server-Sent Events (sse-starlette) |
| Notifications | Microsoft Teams (Adaptive Cards), Bluesky (AT Protocol) |
| Infrastructure | Azure Container Apps, Azure AI Foundry, Docker Compose |

---

## License

MIT
