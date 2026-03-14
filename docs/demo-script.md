# Quipu — 2-Minute Demo Video Script

## Pre-Recording Setup

- **Screen layout**: Split-screen — Quipu dashboard (left/main) + Terminal with Azure live logs (right/smaller)
- **Live logs command**: `az containerapp logs show --resource-group quipu-platform --name quipu-backend --follow --tail 20`
- **Frontend URL**: https://quipu-frontend.blackdesert-9996f71d.eastus.azurecontainerapps.io
- **Have ready**: Microsoft Teams open with your alerts channel
- **Resolution**: 1920x1080, dark mode browser, no bookmarks bar, clean desktop
- **Record with**: OBS, Loom, or QuickTime — no webcam needed, just screen + voiceover
- **IMPORTANT**: Do a dry run before recording — run the query once so data is warm and you know the timing

---

## Script

### [0:00–0:10] The problem — emotional hook

**On screen**: Landing page at `/` — hero section visible: "AI Early Warning for Your Municipality"

**Voiceover**:

> "When earthquakes hit during heavy rainfall in Peru, landslides can follow within hours. But small municipalities have no monitoring systems — they rely on WhatsApp rumors, often too late."

---

### [0:10–0:20] The solution

**Voiceover**:

> "Quipu is a multi-tenant AI early warning platform built with the Microsoft Agent Framework and Azure OpenAI. Seven specialized agents collaborate to monitor disaster signals 24/7 — and alert communities before crises escalate."

**Action**: Click "Get Started" → Microsoft login appears briefly → sign in

---

### [0:20–0:35] Onboarding — show multi-tenant SaaS

**On screen**: Setup wizard appears

**Voiceover**:

> "Any Peruvian municipality can register in minutes. Select your city — say, Arequipa — and nearby cities to monitor are auto-discovered within 100 kilometers."

**Action**: Type "Arequipa", select it, toggle a couple nearby cities (Moquegua, Camana), click Continue.

> "Configure notification channels — Microsoft Teams webhook, Bluesky — and add emergency contacts."

**Action**: Skip through steps 2-3 quickly (or show pre-configured). Click "Finish Setup."

**On screen**: Dashboard loads — map centered on Arequipa with event markers, monitored zone rectangles visible.

---

### [0:35–0:45] The dashboard — scoped to your city

**Voiceover**:

> "The dashboard is scoped to Arequipa. The map shows earthquakes, fires, and disaster alerts within the monitoring zone. The event feed updates in real time."

**On screen**: Point at:
- Event markers on the map (earthquake icons, fire icons)
- The amber rectangle showing the monitored zone boundary
- Header showing "Arequipa — Disaster & Climate Risk Monitor" and "Live" indicator
- Event count in the header

---

### [0:45–1:05] Ask the agents — the core demo

**Voiceover**:

> "The emergency coordinator asks a simple question."

**Action**: Type: **What's the current situation in Arequipa?**

**On screen**: Agent timeline starts expanding. Live Azure logs scroll on the right showing supersteps and tool calls.

**Voiceover** (narrate as agents appear in the timeline):

> "Seven agents investigate in parallel — powered by MagenticOne orchestration.
>
> The Emergency Monitor queries USGS and GDACS for earthquakes and flood alerts.
>
> The Weather Agent detects a rainfall anomaly compared to the 5-year average.
>
> The News Agent scans Google News and ReliefWeb for local disaster coverage.
>
> The Analysis Agent combines all signals — computing a compound risk score that correlates earthquakes, weather, and media activity."

**On screen**: Once the final answer arrives, point at:
- **Risk score card** — score, level, trend arrow, drivers
- **Map** panning to the focus area
- The agent timeline showing 5+ steps completed

> "This compound risk detection — correlating signals across different domains — is what no single data source can do alone."

---

### [1:05–1:20] Notifications — Teams + Bluesky

**Voiceover**:

> "When risk crosses the threshold, Quipu alerts automatically."

**On screen**: Show the alert banner if one appeared. If not, narrate:

> "Alerts are delivered to Microsoft Teams as Adaptive Cards — in Spanish, with risk breakdowns and a link to the dashboard. And public advisories post to Bluesky bilingually, so citizens stay informed too."

**Action**: Briefly switch to Teams to show the card (from the test notification during onboarding, or a real alert).

---

### [1:20–1:35] Background monitoring — the differentiator

**Voiceover**:

> "But Quipu doesn't wait for questions. A background poller runs every five minutes — zero AI cost, pure Python risk computation. When any monitored zone crosses the danger threshold, alerts fire automatically."

**On screen**: Point at the Azure live logs showing:
- `Poll cycle complete: X new events`
- `Auto-risk step complete`

> "That means 24/7 compound risk detection for a municipality that can't afford a monitoring team."

---

### [1:35–1:50] Multi-tenant + public status

**Voiceover**:

> "Each municipality gets their own scoped dashboard, their own notification channels, their own emergency contacts. And every city has a shareable public status page for citizens."

**Action**: Navigate to `/status/arequipa-arequipa` — show the public page with current risk level.

> "No login required — citizens can check their city's risk level anytime."

---

### [1:50–2:00] Closing — deployed on Azure

**On screen**: Return to dashboard or show architecture diagram briefly.

**Voiceover**:

> "Seven AI agents. Real disaster data. Deployed entirely on Azure — Container Apps, PostgreSQL with PostGIS, Azure AI Foundry — for under 50 dollars a month.
>
> Quipu gives small municipalities the same disaster intelligence that only national agencies used to have."

---

## Key Phrases to Say (judges listen for these)

- **"Microsoft Agent Framework"** — say once (0:10 or 1:05)
- **"MagenticOne orchestration"** — say once (0:50)
- **"Azure OpenAI"** — say once (0:10)
- **"compound risk detection"** — say **twice** (0:55 and 1:30)
- **"agents collaborate in parallel"** — say once (0:50)
- **"multi-tenant"** — say once (1:35)
- **"deployed on Azure"** — say once (1:50)
- **"Container Apps, PostgreSQL, Azure AI Foundry"** — say once (1:55)

---

## Tips for Recording

1. **Dry run first** — run the exact query before recording so you know the response time and content
2. **Speed up wait times in editing** — if agent response takes 60+ seconds, cut to 10-15 seconds in post
3. **Keep the Azure logs visible** — this proves production deployment; judges will notice
4. **Move your mouse** — point at risk scores, map markers, agent timeline steps
5. **Speak calmly and clearly** — judges watch many videos; clarity wins over speed
6. **Show the onboarding quickly** — don't spend more than 15 seconds on it, it's impressive but not the core
7. **The agent timeline is your most visual feature** — let it play and narrate over it
8. **End strong** — the closing should feel confident, not rushed

---

## What Judges See (mapped to criteria)

| Criteria (20% each) | What you're showing |
|----------------------|---------------------|
| **Technological Implementation** | 8 live APIs, PostGIS spatial queries, SSE streaming, Azure Entra ID auth, Fernet encryption, multi-tenant schema, dual-mode poller |
| **Agentic Design & Innovation** | 7-agent MagenticOne Orchestration, query classifier, compound risk detection, tenant-scoped agent prompts, background auto-risk (no LLM) |
| **Real-World Impact** | Real earthquakes + fires + rainfall data, automatic alerts to Teams/Bluesky, $41/month Azure deployment, El Nino crisis in Peru right now |
| **UX & Presentation** | Landing page → onboarding wizard → scoped dashboard → agent timeline → Teams cards → public status page. Complete user journey in 2 minutes |
| **Adherence to Category** | Microsoft Agent Framework + Semantic Kernel MagenticOne, Azure OpenAI via Foundry, Azure Container Apps, Azure PostgreSQL, Azure Entra ID, Teams integration |

---

## Submission Checklist

- [ ] Demo video (2 min max) uploaded to YouTube/Vimeo as public/unlisted
- [ ] GitHub repository is public with source code
- [ ] Architecture diagram image included in repo or submission
- [ ] Project description covering: features, functionality, problem solved, technologies
- [ ] Team member info with Microsoft Learn usernames
- [ ] Live deployment URL included in description
