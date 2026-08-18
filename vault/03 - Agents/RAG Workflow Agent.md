# RAG Workflow Agent

#agent #rag #search

> Searches 19,870 indexed n8n workflows **per-component** after the CEO breaks down the problem, giving every agent targeted automation templates as context.

## What It Does

After the CEO breaks the problem into components and classifies the deliverable type, this agent:
1. Takes the CEO's component breakdown (e.g., "IoT sensor data collection", "crop health analysis AI")
2. Searches 19,870 workflows **per-component** using FTS5
3. Scores relevance and classifies matches into three tiers, tagged with which component they match
4. Stores results in shared memory so all 6 agents see per-component matches

## Pipeline Position (v1.3)

```
Problem Statement
  |
  v
CEO (runs FIRST)
  |  → breaks problem into 3-7 components
  |  → classifies deliverable_type: code / workflow / hybrid
  v
RAG Agent (instant, <100ms)
  |  → searches PER-COMPONENT across 19,870 workflows
  |  → tags each match with matched_component
  |  → stores recommendations in shared memory
  |  → fires "workflow_analysis" WebSocket event
  v
BA → Researcher → Architect → Engineer → PPT
     (all see per-component workflow context + deliverable_type)
```

### Why CEO-First?

Previously RAG searched on the raw problem statement (often just 5-10 words). Now CEO expands it first into searchable components, so RAG finds more targeted matches. Example:

**Input:** "Smart agriculture monitoring using IoT"
**CEO components:** `["IoT sensor data collection", "crop health analysis AI", "weather alert notifications", "farmer dashboard", "SMS/WhatsApp alerts"]`
**RAG result:** Each component finds its own relevant workflows independently.

## Workflow Library

| Metric | Value |
|--------|-------|
| **Total workflows** | 19,870 |
| **AI-powered** | 7,806 (39%) |
| **With webhooks** | 3,394 |
| **With databases** | 6,559 |
| **Domain categories** | 27 |
| **Database size** | 43 MB |
| **Search type** | SQLite FTS5 full-text |
| **Index time** | 16 seconds |

### Source Data

Located at `C:\Users\rajes\Downloads\14000+ N8N WORKFLOWS-20260625T045947Z-3-001`

| Source | Count | Organization |
|--------|-------|-------------|
| **4000+ N8N Agents** | 2,294 | By tool (OpenAI, Telegram, Slack, etc.) |
| **4000 Categorized Templates** | ~4,000 | By domain (Healthcare, Agriculture, etc.) |
| **Part 1 + Part 2 Templates** | ~13,000 | Mixed, categorized by node analysis |
| **awesome-n8n-templates** | 336 | GitHub curated (OpenAI, RAG, Telegram, etc.) |

### Top Categories

| Category | Workflows |
|----------|-----------|
| AI & Machine Learning | 5,367 |
| Communication & Notifications | 2,799 |
| Productivity & Workflow | 2,717 |
| Data Analytics & BI | 1,338 |
| DevOps & Infrastructure | 1,147 |
| Integration & API | 729 |
| Document Processing | 493 |
| Social Media & Marketing | 331 |
| Data Collection & Forms | 305 |
| E-Commerce & Retail | 282 |

## Classification System

### Tier 1: Folder-based (from organized directories)
24 pre-existing domain folders: Agriculture, AI_ML, Healthcare, Education, etc.

### Tier 2: Node-based (for uncategorized workflows)
Analyzes actual n8n node types in the workflow JSON to infer category:
- OpenAI/LangChain nodes → AI & Machine Learning
- Gmail/Telegram/Slack → Communication & Notifications
- Postgres/Supabase/Redis → DevOps & Infrastructure
- etc.

### SIH Theme Mapping
Each category maps to SIH's 15 official themes:
- Agriculture → Smart Automation, Disaster Management
- Healthcare → MedTech / BioTech / HealthTech
- Education → Smart Education
- Finance → FinTech, Blockchain & Cybersecurity

## Relevance Scoring

```
base_score = 0.3 (FTS match bonus)
+ name_match_ratio × 0.5
+ (tag + integration + description match) × 0.3
+ AI nodes bonus: +0.10
+ Complex workflow bonus (>5 nodes): +0.05
+ Webhook bonus: +0.05
```

| Tier | Score | Meaning |
|------|-------|---------|
| **Reusable** | 70%+ | Use this workflow directly |
| **Modifiable** | 40-70% | Adapt for the problem |
| **Inspiration** | <40% | Learn from the pattern |

## What Agents See

Every agent's context includes a section like:

```
## Deliverable Type: WORKFLOW
Generate n8n workflow JSON (importable into n8n).

## Existing n8n Workflow Library Analysis
**Found 10 relevant workflows: 3 reusable, 5 need modifications, 2 for inspiration.**
**Components analyzed:** WhatsApp chatbot, AI customer support, ticket classification

### Per-Component Matches
- **WhatsApp chatbot**: WhatsApp Bot (85%), Chat Widget (62%)
- **AI customer support**: AI Support Agent (72%)
- **ticket classification**: No matches — build from scratch

### Reusable Workflows (use directly)
- **WhatsApp Bot** (Communication) — integrations: whatsapp,openai | relevance: 85% [for: WhatsApp chatbot]

### Modifiable Workflows (adapt for this problem)
- **AI Support Agent** (AI & ML) — integrations: telegram,openai | relevance: 55% [for: AI customer support]

### Inspiration Workflows
- Telegram AI-bot (Communication)

**Matched categories:** Healthcare, Communication, AI & ML
**SIH themes:** MedTech / BioTech / HealthTech, Smart Automation
```

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/workflows/analyze` | RAG entry point — problem statement in, recommendations out |
| GET | `/api/workflows/search?q=...` | Free-text search |
| GET | `/api/workflows/categories` | List all categories with counts |
| GET | `/api/workflows/category/{name}` | Browse category |
| GET | `/api/workflows/{id}` | Single workflow detail |

## Deliverable Types (v1.3)

The CEO now classifies each problem's deliverable type:

| Type | When | Engineer Output |
|------|------|----------------|
| `code` | Web apps, APIs, CLI tools | Traditional project files → `.zip` download |
| `workflow` | Automation, agents, chatbots, data pipelines | n8n workflow JSON → `.json` download (importable into n8n) |
| `hybrid` | App + automation (rare) | Both `.zip` AND `.json` |

## Files

| File | Purpose |
|------|---------|
| `backend/app/services/workflow_indexer.py` | Parses 19,870 JSONs into SQLite + FTS5 |
| `backend/app/services/workflow_search.py` | Search service + `analyze_for_problem()` + `analyze_by_components()` |
| `backend/app/services/workflow_generator.py` | Generates downloadable n8n workflow JSON from Engineer output |
| `backend/workflows.db` | SQLite database (gitignored, 43 MB) |

## Rebuilding the Index

```bash
cd backend
python -m app.services.workflow_indexer --source "path/to/workflows" --db workflows.db
```

---

Related: [[Agent Roster]], [[Orchestrator]], [[How It Works]], [[CEO Agent]]
