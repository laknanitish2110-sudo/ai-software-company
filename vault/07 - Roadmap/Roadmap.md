# Roadmap

## V1.0–V1.4 — Hackathon Pipeline (DONE)
**Status:** Complete (Aug 2026)

- [x] 6-agent sequential pipeline (CEO → BA → Researcher → Architect → Engineer → PPT)
- [x] 4 founder approval gates
- [x] Cross-review system
- [x] RAG Workflow Agent (19,870 n8n workflows)
- [x] CEO-first pipeline with deliverable type classification
- [x] Real outputs: ZIP, PPTX, DOCX, n8n JSON
- [x] Deployed: Vercel (frontend) + Railway (backend)

## V2.0 — Persistent AI Employee Platform (DONE)
**Status:** Complete (Sep 2026)

> [!pipeline] The pivot from pipeline tool to AI company platform.

- [x] **Auth + User Accounts** — OAuth (Google/GitHub), JWT sessions
- [x] **Persistent AI Employees** — 6 roles: Sage (BA), Scout (Researcher), Arc (Architect), Atlas (Engineer), Sentinel (QA), Scribe (Writer)
- [x] **Employee Chat** — direct conversation with any employee, with memory
- [x] **Tool System** — function calling, code execution (E2B sandbox)
- [x] **Employee Memory** — 5 types: core, episodic, procedural, semantic, working
- [x] **Memory Consolidation** — dedup, conflict resolution, freshness decay
- [x] **Skill Learning** — employees learn from past work
- [x] **Multi-Employee Delegation** — employees hand off work to each other
- [x] **Async Delegation Worker** — Redis-backed durable task processing
- [x] **Goals Engine** — decompose objectives into task graphs
- [x] **Semantic Memory** — NVIDIA neural embeddings with TF-IDF fallback
- [x] **Billing** — Stripe integration, per-user usage tracking
- [x] **Onboarding** — guided first-time experience
- [x] **Settings** — profile, plan management

## V3.0 — Autonomous Execution Runtime (DONE)
**Status:** Complete (Sep 27, 2026) — Commit `db34a26`

> [!agent] The anti-wrapper differentiator. AI employees that work autonomously with independent quality assurance.

- [x] **Durable Execution Worker** — Redis-backed, SETNX claims, heartbeat, retry, dead-letter queue
- [x] **Employee Execution Policies** — role-specific state machines (Atlas: 8 phases, Scout: 6, etc.)
- [x] **Structured State Transitions** — LLM returns JSON decisions validated against policy transition graph
- [x] **Independent Sentinel Verification** — separate LLM context, never sees builder reasoning
- [x] **Execution Cost Tracking** — per-phase token tracking, budget enforcement
- [x] **Multi-Tier Sentinel** — 3-tier fail-fast: Structural (cheap) → Deep (standard) → Domain (role-specific)
- [x] **Jev Decision Layer** — cheap model (Lightning 30B) for routing/QA, expensive (Super 120B) for creative work
- [x] **"While You Were Away" Reports** — structured work summaries grouped by employee

## V4.0 — Quality Guarantee Platform (IN PROGRESS)
**Status:** Thesis locked, implementation planned

> [!decision] ARIA's core thesis: "We're the only AI that guarantees output quality through independent verification."
> See [[Core Thesis]] for the full strategic argument.

### Locked Features (sequential implementation)

| # | Feature | Description | Status |
|---|---------|-------------|--------|
| 1 | **Verification Proof Engine** | Scorecards showing what Sentinel caught vs what would've shipped raw | Planned |
| 2 | **AI CEO Briefing** | Opinionated daily strategic summary from Jev layer | Planned |
| 3 | **Employee Debate** | Structured disagreement between agents, visible to user | Planned |
| 4 | **Execution Replay** | DVR for AI reasoning, fork from any point | Planned |

### Supporting Work

| Feature | Description | Status |
|---------|-------------|--------|
| E2E Production Test | Execution worker + Sentinel + Jev on Railway with real LLMs | Planned |
| Execution History Page | Dedicated `/executions` route with filtering | Planned |
| Sentinel Dashboard | QA pass/fail rates, cost savings visualization | Planned |
| Cross-Employee Execution | Goals requiring multiple employees orchestrated together | Planned |
| Away Mode | Queue goals and leave — team works autonomously | Planned |

## V5.0 — Org Intelligence (FUTURE)
**Status:** Vision only

| Feature | Description |
|---------|-------------|
| Institutional Memory | AI company remembers everything across all users |
| Self-Improving Agents | Sentinel feedback loops back into employee behavior |
| Model Independence | Hot-swap any LLM provider without behavior changes |
| Agent Marketplace | Share and sell custom employee configurations |

## Design Principles (All Versions)

1. **6 agents, never fewer** — separation of concerns IS the value
2. **Independent verification** — builder never grades its own work
3. **Quality over speed** — we're not the fastest, we're the most reliable
4. **Build for yourself** — this is your tool, not a demo

---

Related: [[Core Thesis]], [[Project Vision]], [[V2 Vision]], [[Gap Analysis]]

#roadmap #planning
