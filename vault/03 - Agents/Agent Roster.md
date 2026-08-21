# Agent Roster

## Overview

| Agent | Role | Approval Gate | Output Format |
|-------|------|--------------|---------------|
| CEO | Project Manager + Classifier | No (auto-approved) | JSON (brief + deliverable_type + components) |
| RAG Agent | Component-based Workflow Search | No (auto, post-CEO) | JSON (per-component workflow recommendations) |
| Business Analyst | Requirements | Yes | JSON |
| Researcher | Market Research | Yes | JSON |
| Architect | Technical Design | Yes | JSON |
| Engineer | Implementation | Yes | JSON -> .zip and/or .json (n8n workflow) |
| PPT | Presentation | No (auto-complete) | JSON -> .pptx file |

## Individual Agents

- [[RAG Workflow Agent]] — searches 19,870 n8n workflows before pipeline starts
- [[CEO Agent]]
- [[Business Analyst Agent]]
- [[Researcher Agent]]
- [[Architect Agent]]
- [[Engineer Agent]]
- [[PPT Agent]]

## Cross-Review Assignments

Each agent's output is reviewed by the most relevant teammate before the Founder sees it:

| Agent Output | Reviewed By | Focus |
|-------------|-------------|-------|
| Business Analyst | CEO | Does analysis match the project brief? |
| Researcher | Business Analyst | Does research cover requirements? |
| Architect | Researcher | Are tech choices research-backed? |
| Engineer | Architect | Does code follow the architecture? |
| PPT | Engineer | Does the presentation match implementation? |

Reviews include a **quality score (1-10)**, alignment check, and hackathon readiness assessment. See [[Cross Review System]] for details.

## LaunchpadX-Optimized Prompts (v1.4)

All agent prompts tuned for LaunchpadX hackathon (theme: Agentic AI / GenAI / Agent Building):

| Agent | LaunchpadX Optimization |
|-------|------------------------|
| CEO | Agentic AI expansion examples (code review agent, support chatbot, research assistant), agent design patterns context |
| BA | AI agent ecosystem constraints (LLM cost, hallucination, latency), tech-focused Indian personas (SNIST Hyderabad) |
| Researcher | Agent frameworks (LangChain, CrewAI, AutoGen), LLM providers, vector DBs, production AI tooling |
| Architect | Agent pipeline design, LLM integration, RAG pipeline, tool calling, memory strategies, cost-per-query |
| Engineer | Showcase agentic AI patterns, agent DOING something for demo, LLM error handling |
| PPT | LaunchpadX judge criteria (agent innovation, technical depth, demo quality, agentic AI understanding) |

## Pipeline Order (v1.3)

```
CEO (FIRST) → RAG → BA → Researcher → Architect → Engineer → PPT
```

CEO runs first to:
1. Break problem into 3-7 searchable components
2. Classify `deliverable_type` as `code`, `workflow`, or `hybrid`

RAG then searches per-component using the CEO's breakdown, not the raw input.

## RAG Workflow Agent (v1.3)

After CEO breaks the problem into components, the RAG agent searches **19,870 indexed n8n workflows** per-component. Results tagged with `matched_component` are stored in shared memory.

| Metric | Value |
|--------|-------|
| **Workflows indexed** | 19,870 |
| **Categories** | 27 domain categories |
| **AI-powered workflows** | 7,806 (39%) |
| **Search engine** | SQLite FTS5 full-text search |
| **Search mode** | Per-component (from CEO breakdown) |
| **Response time** | Instant (<100ms) |

The agent classifies matches into three tiers:
- **Reusable** (relevance 70%+) — use directly
- **Modifiable** (40-70%) — adapt for this problem
- **Inspiration** (<40%) — patterns to learn from

## Deliverable Types (v1.3)

| Type | Output | Example |
|------|--------|---------|
| `code` | .zip with project files | "Student portal for attendance" |
| `workflow` | .json importable into n8n | "AI chatbot for WhatsApp support" |
| `hybrid` | Both .zip and .json | "E-commerce with inventory automation" |

See [[RAG Workflow Agent]] for details.

## Key Design Decisions

1. **Never consolidate roles** — each agent thinks differently about the same problem. A BA focuses on requirements, a Researcher on what exists, an Architect on how to build. Merging loses the focused perspective.

2. **JSON output** — every agent returns structured JSON, making it parseable, displayable, and storable. The Engineer's JSON includes complete file contents that get extracted to real files.

3. **Context inheritance** — each agent receives all previously approved outputs. The Architect sees the BA requirements AND the Research findings. The Engineer sees everything.

4. **Revision feedback** — when rejected, the agent gets the founder's feedback via shared memory and regenerates with that guidance.

Related: [[How It Works]], [[Orchestrator]], [[Cross Review System]]
