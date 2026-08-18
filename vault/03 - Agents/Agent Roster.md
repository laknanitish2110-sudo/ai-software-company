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

## SIH-Optimized Prompts (v1.1)

All agent prompts were tuned for SIH hackathon context:

| Agent | SIH Optimization |
|-------|-----------------|
| CEO | 3 expansion examples for ultra-short inputs, Indian gov context (PM Kisan, DIKSHA) |
| BA | Indian personas mandatory (e.g., "Priya, Gram Panchayat secretary in MP"), DPDP Act 2023, 24h scope |
| Researcher | Bhashini API, IndiaAI, prior SIH winners, Indian sources (YourStory, Inc42) |
| Architect | Indian scale (1.4B people, 500M smartphones), Railway/Render hosting, UPI payments |
| Engineer | Indian locale (INR, IST, pincode), Indian sample data, 3-command setup |
| PPT | SIH judge criteria, Indian statistics and examples |

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
