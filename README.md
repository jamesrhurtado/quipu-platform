# SENTINEL

**Real-time disaster intelligence for Latin America, powered by multi-agent AI.**

Sentinel is an autonomous monitoring system that continuously ingests data from 7 live sources — USGS, GDACS, NASA EONET, NASA FIRMS, GDELT, ReliefWeb, and Bluesky — and uses a team of specialized AI agents to analyze, correlate, and deliver actionable risk assessments through a real-time dashboard.

Ask a question in natural language. Sentinel figures out which agents to activate, queries the right APIs, scores source reliability, computes a composite risk assessment, and presents findings on an interactive map — all in seconds.

![Python](https://img.shields.io/badge/python-3.13-blue)
![Next.js](https://img.shields.io/badge/next.js-14-black)
![Semantic Kernel](https://img.shields.io/badge/semantic--kernel-1.39-purple)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Why Sentinel Exists

When a 7.2 earthquake hits Peru, information fractures across dozens of sources: USGS reports the seismology, GDACS estimates impact, NASA detects landslide risk, news outlets report casualties at different speeds, and social media fills with unverified claims. Emergency coordinators must manually piece this together under time pressure.

Sentinel automates that synthesis. It treats each data domain as a specialist agent, orchestrates them dynamically based on the query, and produces a confidence-weighted intelligence report — not just raw data, but assessed, scored, and actionable.

---

## Architecture

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
│  │  │          │ │Agent     │ │Agent     │ │              │   │ │
│  │  │• USGS    │ │• GDELT   │ │• NASA    │ │• PostGIS     │   │ │
│  │  │• GDACS   │ │• Bluesky │ │  FIRMS   │ │• Risk Engine │   │ │
│  │  │• EONET   │ │• Relief  │ │          │ │• Sitreps     │   │ │
│  │  │• PostGIS │ │  Web     │ │          │ │              │   │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │ │
│  │       │              │           │              │            │ │
│  │       └──────────────┴───────────┴──────────────┘            │ │
│  │                    Source Scoring Layer                       │ │
│  │              (reliability × freshness weights)               │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ Background   │  │ SSE Manager  │  │ Risk Escalation       │  │
│  │ Poller (5m)  │  │ (real-time)  │  │ Engine                │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                │  PostgreSQL +     │
                │  PostGIS          │
                └───────────────────┘
```

### Two-Tier Design

**Tier 1 — Background Poller (no LLM, runs continuously)**
A lightweight loop polls USGS, GDACS, NASA EONET, and FIRMS every 5 minutes, normalizes events, and upserts them into PostGIS. New events stream to the frontend via SSE. This keeps the dashboard populated at near-zero cost.

**Tier 2 — Agent Orchestration (LLM, on-demand)**
When a user asks a question, the system activates. A keyword classifier determines which agents are relevant — a fire query skips the emergency and social agents entirely. Selected agents run in parallel via Semantic Kernel's MagenticOrchestration, each calling live APIs with their specialized tools. Results flow through a scoring layer that attaches reliability and freshness weights before the manager synthesizes everything into a final intelligence report.

---

## Key Features

### Dynamic Agent Selection
Queries are classified at intake. `"Are there fires in the Amazon?"` activates only FireMonitor + Analysis. `"What's happening in Peru?"` activates all four agents. The reasoning is transparent — every query produces a classification event explaining why specific agents were chosen.

### Probabilistic Source Scoring
Every tool result carries two scores:
- **Reliability** — static weight per source (USGS: 1.0, GDACS: 0.9, GDELT: 0.6, Bluesky: 0.4)
- **Freshness** — linear decay from 1.0 (now) to 0.0 (7 days old), computed from actual data timestamps

The manager weighs these when synthesizing, explicitly stating confidence: *"High confidence (USGS + GDACS corroborate)"* vs *"Moderate confidence (news-based only)"*.

### Composite Risk Engine
A weighted formula combines four normalized components:

| Component | Weight | Source |
|-----------|--------|--------|
| Event severity | 35% | Max severity from disaster events (1-5) |
| Fire density | 20% | Active fire count vs baseline |
| Media spike | 20% | Article count vs baseline |
| Data confidence | 25% | Average (reliability × freshness) |

Output: **Normal** (1-2.9), **Elevated** (3-3.9), or **Critical** (4-5). Persisted to database for trend analysis.

### Agent Reasoning Timeline
Every orchestration step is timed and streamed to the frontend as it happens:
```
🧠 Manager    → Selected EmergencyMonitor + AnalysisAgent     0.2s
🌍 Emergency  → Found 3 earthquakes M3.5+ in Peru             1.8s
📊 Analysis   → Risk score computed: ELEVATED (3.2/5)         3.1s
✅ Manager    → Synthesizing intelligence report               4.0s
```
Live during processing, collapsible after completion.

### Structured Intelligence Output
Every response ends with machine-readable structured data: risk assessment, source breakdown, map focus coordinates, and recommendations. The frontend uses this to render a risk score card and automatically pan the map to the relevant region.

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
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
NASA_FIRMS_MAP_KEY=your-firms-key    # Get free at https://firms.modaps.eosdis.nasa.gov/api/area/
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

---

## Project Structure

```
sentinel-agent/
├── backend/
│   ├── agents/
│   │   ├── classifier.py        # Query → agent routing
│   │   ├── definitions.py       # Orchestration, timeline, structured output
│   │   ├── instructions.py      # Agent system prompts
│   │   ├── risk_engine.py       # Composite risk scoring
│   │   ├── scoring.py           # Source reliability + freshness
│   │   └── tools/
│   │       ├── emergency.py     # USGS, GDACS, EONET, PostGIS
│   │       ├── social.py        # GDELT, Bluesky, ReliefWeb
│   │       ├── satellite.py     # NASA FIRMS
│   │       └── analysis.py      # DB analytics, sitreps, risk assessment
│   ├── api/routes/
│   │   ├── events.py            # GET /api/events
│   │   ├── query.py             # POST /api/query (SSE stream)
│   │   ├── risk.py              # GET /api/risk-assessments
│   │   └── stream.py            # SSE /api/stream (live events)
│   ├── services/
│   │   ├── poller.py            # Background data ingestion
│   │   ├── bluesky_buffer.py    # Bluesky Jetstream consumer
│   │   ├── normalizer.py        # Raw → normalized event mapping
│   │   └── sse_manager.py       # Server-sent events broadcaster
│   ├── sql/schema.sql           # PostGIS schema
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

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | [Semantic Kernel](https://github.com/microsoft/semantic-kernel) (MagenticOrchestration) |
| LLM | Azure OpenAI GPT-4o + GPT-4o-mini |
| Backend | Python 3.13, FastAPI, asyncpg, httpx |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Map | Leaflet + leaflet.markercluster |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Real-time | Server-Sent Events (sse-starlette) |
| Infrastructure | Docker Compose |

---

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Yes | Azure OpenAI API key |
| `NASA_FIRMS_MAP_KEY` | No | Enables fire detection (free at [FIRMS](https://firms.modaps.eosdis.nasa.gov/api/area/)) |
| `NASA_API_KEY` | No | NASA API key (defaults to `DEMO_KEY`) |
| `BLUESKY_ENABLED` | No | Set `true` to enable real-time social feed (default: `false`) |
| `POLL_INTERVAL_SECONDS` | No | Background poll frequency (default: `300`) |

---

## License

MIT
