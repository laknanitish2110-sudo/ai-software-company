# Our AI Software Company — Through the Agentic AI Lens

How our project maps to every concept in the agentic AI world. Use this page when explaining the project to hackathon judges.

---

## What We Built

A **multi-agent AI system** that takes a problem statement and autonomously produces a complete software project — from business analysis to working code to presentation slides.

6 specialized AI agents work as a team, passing their work through a sequential pipeline with human approval gates.

---

## Mapping to Agent Types

| Our Agent | Agent Type (Russell & Norvig) | Architecture |
|-----------|-------------------------------|-------------|
| [[CEO Agent]] | **Goal-based** — has explicit goal to decompose the problem | Deliberative |
| [[Business Analyst Agent]] | **Model-based** — maintains model of user needs | Deliberative |
| [[Researcher Agent]] | **Learning-like** — adapts search based on findings | Hybrid (reactive tool use + deliberative analysis) |
| [[Architect Agent]] | **Utility-based** — optimizes for feasibility + quality trade-offs | Deliberative |
| [[Engineer Agent]] | **Goal-based** — generates code to satisfy architecture spec | Hybrid (planning + tool use) |
| [[PPT Agent]] | **Model-based** — synthesizes all prior outputs into narrative | Deliberative |

**Overall system:** Hierarchical Multi-Agent System

---

## Mapping to Design Patterns

| Pattern | How We Use It |
|---------|--------------|
| **Tool Use** | Researcher calls Tavily web search; Engineer generates files; PPT creates .pptx |
| **ReAct** | Each agent reasons about context → generates output → validates JSON |
| **Reflection** | Cross-review system — agents critique each other's work |
| **Planning** | CEO creates the master plan; Orchestrator executes it |
| **Multi-Agent** | 6 specialized agents with distinct roles |
| **Sequential** | Fixed pipeline: CEO→BA→Researcher→Architect→Engineer→PPT |
| **Human-in-the-Loop** | 4 approval gates where the Founder reviews and approves/rejects |

We use **6 out of 7** major design patterns. Only pattern we don't use: Swarm (we chose sequential over peer-to-peer).

---

## Mapping to Architecture

| Concept | Our Implementation |
|---------|-------------------|
| **Architecture type** | Pipeline (sequential chain) |
| **Communication** | Shared memory (database) + event-driven (WebSocket) |
| **Orchestration** | Custom orchestrator (`orchestrator.py`) |
| **State management** | SQLite database + in-memory state |
| **Tool protocol** | Direct API calls (not MCP — custom integration) |
| **Framework** | None — custom-built on FastAPI + OpenRouter |

---

## Mapping to Frameworks

We built custom instead of using a framework. Here's where our design aligns:

| Framework Concept | Our Equivalent |
|------------------|----------------|
| CrewAI's **Agents with Roles** | Our 6 agents with distinct system prompts |
| CrewAI's **Tasks** | Our pipeline stages |
| LangGraph's **State** | Our database + shared memory |
| LangGraph's **Edges** | Our orchestrator's `_start_next_agent()` |
| OpenAI SDK's **Handoffs** | Our sequential output passing |
| LangGraph's **Human-in-the-loop** | Our approval gates |

---

## Technical Differentiators (for Judges)

1. **Not just a chatbot** — It's a full multi-agent system with 6 specialized roles
2. **Real output** — Downloads actual .zip code, .pptx presentation, .docx report
3. **Human oversight** — 4 approval gates prevent runaway AI
4. **Cross-review** — Agents review each other (BA reviews CEO, Researcher reviews BA, etc.)
5. **Web-grounded research** — Researcher uses live web search, not just training data
6. **Streaming transparency** — Watch agents think in real-time via WebSocket
7. **Demo resilience** — Cached demo mode for reliable hackathon presentations
8. **Cost-optimized** — Free models for analysis, paid model only for code generation ($0.26/run)

---

## The Pitch (30-second version)

> "We built an AI software company — a team of 6 AI agents that work together like a real startup. You give it a problem, and the CEO plans, the Business Analyst defines requirements, the Researcher investigates the market, the Architect designs the system, the Engineer writes actual code, and the Presentation specialist creates your pitch deck. It's not one AI doing everything — it's six specialists collaborating, with human approval at every critical step. The output? A downloadable codebase, a PowerPoint presentation, and a Word document — all from a single problem statement."

---

See [[Agentic AI - Master Guide]] | [[Agent Design Patterns]] | [[Multi-Agent Architectures]] | [[Pipeline Flow]]

#agentic-ai #our-project #hackathon #pitch
