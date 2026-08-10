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

## V1.5 — Level 4 Engineer
**Goal:** Engineer agent auto-deploys generated projects

> [!pipeline] Level 4 Upgrade
> The Engineer currently generates code as a `.zip` download. Level 4 makes it **auto-deploy**:

| Feature | Description | Status |
|---------|-------------|--------|
| **GitHub Integration** | Auto-create repo, push generated code | Planned |
| **Vercel Deploy** | Auto-deploy from GitHub, return live URL | Planned |
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

Related: [[Project Vision]], [[How It Works]], [[Pipeline Test Results]], [[Model Strategy]], [[n8n Integration]]

#roadmap #planning
