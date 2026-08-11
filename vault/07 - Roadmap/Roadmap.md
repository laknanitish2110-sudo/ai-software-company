# Roadmap

## V1.0 — Hackathon MVP (DONE)
**Target:** Aug 18-19, 2026 hackathon
**Status:** Complete

### What's built
- [x] 6-agent sequential pipeline (CEO -> BA -> Researcher -> Architect -> Engineer -> PPT)
- [x] 4 founder approval gates (BA, Researcher, Architect, Engineer)
- [x] Cross-review system — agents review each other's output
- [x] Shared project memory across all agents
- [x] Real-time WebSocket activity feed
- [x] Call Employee — direct chat with any agent
- [x] Engineer pair programming iteration mode
- [x] Code generation -> downloadable `.zip` with runnable project
- [x] PPTX generation -> downloadable `.pptx` presentation
- [x] DOCX generation -> downloadable `.docx` documentation
- [x] Web search via Tavily (AI-optimized search) for Researcher
- [x] Light theme dashboard with pipeline visualization
- [x] n8n webhook integration (5 event types, 12 events per run)
- [x] Share buttons (Google Drive, Sheets, Email, Share All)
- [x] OmniRoute AI gateway for model routing
- [x] End-to-end test with all deliverables (see [[Pipeline Test Results]])
- [x] Model strategy — free models + Claude Sonnet 4 for Engineer (see [[Model Strategy]])

## V1.1 — Deployed + Polished (DONE)
**Completed:** 2026-08-11
**Status:** Complete

### What's new
- [x] **Backend deployed on Railway** — live at `ai-software-company-production.up.railway.app`
- [x] **Frontend deployed on Vercel** — live at `frontend-wheat-ten-gla6y29t60.vercel.app`
- [x] **SIH-optimized agent prompts** — all 6 agents tuned for ultra-short SIH inputs (median 72 chars)
  - CEO: 3 concrete expansion examples, Indian context (PM Kisan, DIKSHA, CSC centres)
  - BA: Indian personas mandatory, DPDP Act 2023, 2G connectivity, 24h scope
  - Researcher: Bhashini API, IndiaAI, prior SIH winners, Indian startup sources
  - Architect: Railway/Render hosting, Indian scale (1.4B people), Razorpay/PhonePe UPI
  - Engineer: Indian locale (INR, IST, pincode), 3-command setup
  - PPT: SIH judge criteria, Indian statistics
- [x] **Skeleton loading states** — shimmer animation loaders replacing blank screens
  - DashboardSkeleton, SkeletonCanvas, SkeletonOutputCard, SkeletonActivity
  - CSS `@keyframes shimmer` and `@keyframes pulseSubtle` animations
- [x] **Enhanced peer review system**
  - Quality score (1-10) with color-coded badge (green/blue/yellow/red)
  - Role-specific review criteria (5 questions per role, SIH-focused)
  - PPT agent now reviewed by Engineer
  - Alignment check and hackathon readiness fields
- [x] **Toast notification system** — success/error/warning/info toasts with auto-dismiss
- [x] **WebSocket disconnect banner** — visual warning + auto-reconnect
- [x] **Agent introspection panel** — view token usage, model, processing time
- [x] **CORS configuration** — regex match for `*.vercel.app` domains
- [x] **Health endpoint** — `GET /health` for Railway monitoring

## V1.2 — RAG Workflow Agent (DONE)
**Completed:** 2026-08-11
**Status:** Complete

### What's new
- [x] **RAG Workflow Agent** — searches 19,534 n8n workflows before pipeline starts
  - Workflow indexer: parses JSONs into SQLite with FTS5 full-text search
  - 27 domain categories, SIH theme mapping
  - 7,554 AI-powered workflows identified (39%)
  - Three-tier classification: reusable / modifiable / inspiration
- [x] **Auto-wired into pipeline** — runs before CEO, results in shared memory for all agents
- [x] **5 new API endpoints** — `/workflows/analyze`, `/search`, `/categories`, etc.
- [x] **Node-based categorization** — uncategorized workflows classified by their n8n node types

## V1.5 — Level 4 Engineer
**Goal:** Engineer agent auto-deploys generated projects

> [!pipeline] Level 4 Upgrade
> The Engineer currently generates code as a `.zip` download. Level 4 makes it **auto-deploy**:

| Feature | Description | Status |
|---------|-------------|--------|
| **GitHub Auto-Create** | Auto-create repo, push generated code | Planned |
| **Vercel Auto-Deploy** | Auto-deploy from GitHub, return live URL | Planned |
| **Interactive Build** | Founder watches code appear in real-time editor | Planned |
| **Live Preview** | Generated app running at a real URL, not a ZIP | Planned |
| **Iteration Mode** | Edit code in-browser, re-deploy instantly | Planned |

See [[GitHub Integration]] and [[Engineer Agent]] for details.

## V2.0 — Post-Hackathon Product
**Goal:** Reliable personal tool for solo devs

| Feature | Why | Status |
|---------|-----|--------|
| Agent memory persistence | Agents learn from past projects | Planned |
| Project history dashboard | Browse and compare past projects | Planned |
| Template projects | Pre-built pipelines for common hackathon types | Planned |
| Custom agent prompts | Users define their own agent behaviors | Planned |
| Theme toggle | Light/dark mode switch | Planned |
| Multiple model presets | Quick-switch between free-only and quality modes | Planned |

## V3.0 — Multi-User Platform
**Goal:** Other solo devs can use it

| Feature | Why | Status |
|---------|-----|--------|
| User authentication | Multiple users, separate workspaces | Planned |
| Cloud deployment | Accessible from anywhere, not localhost | Planned |
| Parallel agents | Run Researcher + Architect simultaneously | Planned |
| Agent-to-agent chat | Agents discuss before presenting to founder | Planned |
| Marketplace | Share and sell custom agent configurations | Planned |

## Model Strategy

> [!decision] Cost-Optimized Model Split
> | Agent | Model | Cost |
> |-------|-------|------|
> | CEO, BA, Researcher, PPT | Gemma 4 31B | Free |
> | Architect | DeepSeek V3 | Free |
> | Engineer | Claude Sonnet 4 | ~$0.25/run |
> | Cross-Reviews | Gemma 4 31B | Free |
> | **Total per run** | | **~$0.26** |
>
> Budget of $10 = 38+ full pipeline runs. See [[Model Strategy]] for details.

## n8n Integration

> [!status] Webhook Event Hub
> - Instance: `srv1867770.hstgr.cloud`
> - 5 event types routed: `agent_completed`, `founder_decision`, `project_completed`, `share`, `research_completed`
> - 12/12 events delivered in test run
> - See [[n8n Integration]] for full setup

## Design Principles (All Versions)

1. **6 agents, never fewer** — separation of concerns IS the value
2. **Founder always in control** — approval gates are non-negotiable
3. **Real outputs** — runnable code, real presentations, not just text
4. **Build for yourself** — this is your tool, not a demo for judges

---

Related: [[Project Vision]], [[How It Works]], [[Pipeline Test Results]], [[Model Strategy]], [[n8n Integration]], [[GitHub Integration]]

#roadmap #planning
