# Persistent AI Employee Platform — Design Document

**Status:** DRAFT — awaiting review
**Date:** 2026-09-24
**Scope:** Evolve ARIA from stateless agent pipeline → persistent AI employee platform

---

## 1. Executive Summary

ARIA currently runs 6–8 stateless agents per pipeline execution. Agents have no memory across projects, no persistent identity, and no ability to continue work across sessions. This design transforms ARIA into a platform where **the employee is the primary object**, not the conversation or the pipeline run.

**What we're building:** A persistent digital worker with identity, memory, skills, tools, workspace, and cross-session continuity.

**What we're NOT building (yet):** Multi-employee collaboration (V3), autonomous routines (V2), browser automation (V4).

---

## 2. What We Already Have (Reuse Map)

| Capability | Existing Asset | Reuse | Gap |
|---|---|---|---|
| Agent roles & prompts | `agents/prompts.py`, `AgentRole` enum | Identity seed — role, system prompt, model preference | No persistence, no cross-session memory |
| Execution state machine | `execution_schema.py`, orchestrator | Task lifecycle — QUEUED→RUNNING→COMPLETED | Scoped to single pipeline run, not employee lifetime |
| Project-scoped memory | `shared_memory` table, `conversations` table | Working memory within a project | No employee-level memory, no cross-project recall |
| Cross-project knowledge | `domain_learnings` table, `domain_memory.py` | Semantic memory prototype | Keyword-only retrieval, no confidence/freshness, no per-employee scoping |
| Code execution | E2B sandbox, `sandbox_runner.py` | Employee workspace/computer | Ephemeral per-run, no persistent workspace |
| Artifact storage | `artifact_store.py` (local filesystem) | Employee artifact output | No cloud storage, no artifact versioning |
| Tool integrations | GitHub, web search, n8n, security gate | Employee tool belt | No permission model per-employee |
| Approval flow | Atomic status CAS, auto-approve mode | Human-in-the-loop approval engine | No fine-grained permission matrix |
| Redis coordination | Locks, pub/sub, rate limits, budgets | Employee communication bus | Already supports multi-worker coordination |
| LLM multi-provider | engine.py with Groq→NVIDIA→Bytez→OpenRouter | Brain abstraction (model-swappable) | Already model-agnostic |
| Repair loop | `repair_loop.py` + IQA + regression | Procedural skill: "debug and fix code" | Hardcoded, not a reusable skill definition |
| Frontend | Next.js + project dashboard | Employee interaction UI | Needs employee-centric redesign |

**Key insight:** ~60% of the infrastructure exists. The biggest gaps are persistence layer (employee identity + memory tables), memory engine (lifecycle + retrieval), and the employee runtime (state machine that spans sessions).

---

## 3. Database Schema — New & Modified Tables

### 3.1 New Tables

```sql
-- The persistent employee
CREATE TABLE employees (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,               -- "Atlas"
    role        TEXT NOT NULL,               -- "Senior Software Engineer"
    persona     TEXT,                        -- system prompt / personality
    avatar_url  TEXT,
    status      TEXT NOT NULL DEFAULT 'idle', -- idle | working | paused | archived
    config      TEXT,                        -- JSON: model preferences, tool config
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX idx_employees_user ON employees(user_id);

-- The 5-type memory store
CREATE TABLE memories (
    id              TEXT PRIMARY KEY,
    employee_id     TEXT NOT NULL REFERENCES employees(id),
    type            TEXT NOT NULL,           -- working | episodic | semantic | preference | procedural
    content         TEXT NOT NULL,           -- the memory itself
    source          TEXT,                    -- where it came from: conversation, tool_output, consolidation
    source_id       TEXT,                    -- reference to conversation/task/artifact
    confidence      REAL NOT NULL DEFAULT 0.8,
    importance      REAL NOT NULL DEFAULT 0.5,  -- 0-1 for retrieval ranking
    tags            TEXT,                    -- JSON array of searchable tags
    embedding_id    TEXT,                    -- reference to vector store entry (nullable until V1b)
    created_at      TEXT NOT NULL,
    last_accessed   TEXT,
    last_verified   TEXT,
    stale_after     TEXT,                    -- nullable; memory expires after this
    superseded_by   TEXT,                    -- if a newer memory replaces this one
    is_active       INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_memories_employee ON memories(employee_id);
CREATE INDEX idx_memories_type ON memories(employee_id, type);
CREATE INDEX idx_memories_active ON memories(employee_id, is_active);

-- Employee sessions (replaces ephemeral pipeline runs)
CREATE TABLE employee_sessions (
    id              TEXT PRIMARY KEY,
    employee_id     TEXT NOT NULL REFERENCES employees(id),
    project_id      TEXT REFERENCES projects(id),  -- nullable: some sessions aren't project-scoped
    status          TEXT NOT NULL DEFAULT 'active', -- active | completed | paused | abandoned
    summary         TEXT,                    -- LLM-generated session summary (written on completion)
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    last_activity   TEXT NOT NULL
);
CREATE INDEX idx_sessions_employee ON employee_sessions(employee_id);

-- Session messages (chat history within a session)
CREATE TABLE session_messages (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES employee_sessions(id),
    role            TEXT NOT NULL,           -- user | employee | system | tool
    content         TEXT NOT NULL,
    tool_calls      TEXT,                    -- JSON: tool invocations in this message
    tool_results    TEXT,                    -- JSON: tool results
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_messages_session ON session_messages(session_id);

-- Employee skills (V2, but schema designed now)
CREATE TABLE skills (
    id              TEXT PRIMARY KEY,
    employee_id     TEXT REFERENCES employees(id),  -- nullable = shared/global skill
    name            TEXT NOT NULL,
    description     TEXT,
    trigger_when    TEXT,                    -- condition description
    steps           TEXT NOT NULL,           -- JSON: ordered steps
    validation      TEXT,                    -- JSON: how to verify success
    approval_rules  TEXT,                    -- JSON: what needs human approval
    source          TEXT DEFAULT 'manual',   -- manual | learned
    use_count       INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Employee tool permissions
CREATE TABLE tool_permissions (
    id              TEXT PRIMARY KEY,
    employee_id     TEXT NOT NULL REFERENCES employees(id),
    tool            TEXT NOT NULL,           -- github | e2b | terminal | browser | database | deploy
    action          TEXT NOT NULL,           -- read | write | execute | delete | approve
    permission      TEXT NOT NULL DEFAULT 'ask',  -- allow | ask | deny
    granted_by      TEXT,                    -- user_id who set this
    updated_at      TEXT NOT NULL,
    UNIQUE(employee_id, tool, action)
);
```

### 3.2 Modified Tables

```sql
-- projects: add employee_id (which employee is working on this)
ALTER TABLE projects ADD COLUMN employee_id TEXT REFERENCES employees(id);

-- executions: link to employee session
ALTER TABLE executions ADD COLUMN session_id TEXT REFERENCES employee_sessions(id);
```

### 3.3 Tables We Keep As-Is

- `users` — unchanged
- `agent_outputs` — still used for pipeline step outputs within an execution
- `shared_memory` — still used for intra-pipeline state
- `conversations` — still used for agent-level chat within pipeline
- `cost_tracking` — add employee_id column for per-employee cost reporting
- `execution_events` — unchanged
- `domain_learnings` — evolves into seed data for semantic memories

---

## 4. Memory Engine

### 4.1 Architecture

```
              User message / Tool result
                        │
                        ▼
              ┌──────────────────┐
              │ Memory Candidate │
              │   Extractor      │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Should we        │
              │ remember this?   │──── NO ──→ discard
              └────────┬─────────┘
                       │ YES
                       ▼
              ┌──────────────────┐
              │ Classify         │
              │ (type + tags)    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Dedup / merge    │
              │ with existing    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Store            │
              │ (DB + optional   │
              │  vector embed)   │
              └──────────────────┘
```

### 4.2 Implementation Plan (V1a → V1b)

**V1a (ship first):** Explicit memory only.
- User says "remember X" → store with type + confidence 1.0
- User says "forget X" → mark is_active=0
- Employee asks "what do you know about X?" → keyword search on memories table
- Working memory = current session context (session_messages + project state)
- No automatic extraction, no embeddings, no consolidation

**V1b (add after V1a feedback):** Automatic extraction.
- After each session ends, run a memory extraction pass:
  - LLM prompt: "Given this session transcript, extract any facts, preferences, or procedures worth remembering long-term."
  - Classify each extracted memory
  - Dedup against existing memories (exact + fuzzy match)
  - Store with confidence based on extraction confidence
- Add embedding generation (via LLM embedding API) for semantic retrieval
- Implement freshness checking: if `stale_after < now`, flag for re-verification

### 4.3 Retrieval Flow

```
Employee receives task
        │
        ▼
  Intent analysis (what does this task need?)
        │
        ▼
  Memory query (filter by type, tags, project)
        │
        ▼
  Rank by: relevance × confidence × freshness
        │
        ▼
  Top-K memories (K=10-20, configurable)
        │
        ▼
  Inject into employee's context window
        │
        ▼
  LLM reasoning with memory-augmented context
```

**V1a retrieval:** Simple SQL query on memories table, filtered by employee_id + type + keyword search on content/tags. Rank by importance × confidence.

**V1b retrieval:** Add vector similarity search. Hybrid: SQL filter first (type, active, not stale), then rank by embedding cosine similarity × confidence × recency.

### 4.4 Consolidation (V1b+)

Runs periodically (every N sessions or on-demand):

1. Group related memories by tags/topic
2. LLM prompt: "These N memories are about the same topic. Produce one consolidated memory and flag any contradictions."
3. Supersede old memories (set `superseded_by` on originals)
4. Store consolidated memory with higher confidence
5. For factual memories, verify against authoritative sources before consolidation

### 4.5 What Goes Where

| Data | Store | Why |
|---|---|---|
| Employee state, memories, sessions | PostgreSQL | Structured, queryable, transactional |
| Memory embeddings | Vector store (pgvector extension) | Semantic similarity search |
| Generated files, artifacts | Artifact store (local → S3) | Large blobs, versioned |
| Current task state, locks | Redis | Fast, ephemeral, pub/sub |
| Code truth | Git/GitHub | Authoritative, versioned |
| Live deployment state | CI/CD APIs | Authoritative, don't cache |

---

## 5. Employee Runtime

### 5.1 State Machine

```
                    ┌─────────┐
          create    │  IDLE   │
         ─────────→ │         │◄──────────────┐
                    └────┬────┘               │
                         │ receive_task       │ task_complete
                         ▼                    │ / timeout
                    ┌─────────┐               │
                    │ WORKING │───────────────┘
                    │         │
                    └────┬────┘
                         │ needs_approval
                         ▼
                    ┌─────────┐
                    │ BLOCKED │──→ approval_received ──→ WORKING
                    │         │
                    └────┬────┘
                         │ user_pauses
                         ▼
                    ┌─────────┐
                    │ PAUSED  │──→ user_resumes ──→ WORKING
                    └─────────┘

                    ┌──────────┐
                    │ ARCHIVED │  (soft delete, memories preserved)
                    └──────────┘
```

### 5.2 Session Lifecycle

```
1. User opens employee chat (or employee receives scheduled task)
2. Create or resume employee_session
3. Load context:
   a. Employee identity (name, role, persona)
   b. Relevant memories (retrieval flow)
   c. Current session messages (if resuming)
   d. Active project state (if project-scoped)
4. Employee processes user message:
   a. Augment with memory context
   b. LLM reasoning
   c. Tool execution (if needed)
   d. Permission check (if tool requires approval)
   e. Generate response
5. Store session_message
6. Extract memory candidates (V1b)
7. Repeat 4-6 until session ends
8. On session end:
   a. Generate session summary
   b. Run memory extraction (V1b)
   c. Update employee status → idle
```

### 5.3 How Current Pipeline Maps to Employee Runtime

The existing 6-agent pipeline becomes **one mode** of an employee's work:

```
User: "Build me a task management app"
        │
        ▼
  Atlas (Employee) receives task
        │
        ▼
  Atlas decides: "This needs the full build pipeline"
        │
        ▼
  Atlas invokes pipeline as a tool/skill:
    CEO analysis → BA requirements → Architect design →
    Engineer code → QA validation → Repair if needed
        │
        ▼
  Atlas reports result to user
  Atlas stores memories from the experience
```

The key shift: the pipeline is a **tool the employee uses**, not the employee itself.

But for V1, the pipeline still runs the same way internally — we're wrapping it in the employee runtime, not rewriting it.

---

## 6. Tool Permission Model

### 6.1 Permission Matrix (Defaults)

| Tool | Read | Write | Execute | Delete | Approve |
|---|---|---|---|---|---|
| GitHub | allow | ask | — | deny | ask |
| E2B Sandbox | allow | allow | allow | allow | — |
| Terminal | allow | — | ask | — | — |
| Files/Artifacts | allow | allow | — | ask | — |
| Database | allow | ask | — | deny | — |
| Deploy | allow | — | deny | — | deny |
| Web Search | allow | — | — | — | — |
| Send Notification | — | — | ask | — | — |

### 6.2 Permission Check Flow

```
Employee wants to use tool
        │
        ▼
  Check tool_permissions table
        │
  ┌─────┼──────────┐
  ↓     ↓          ↓
allow   ask       deny
  │     │          │
  │     ▼          ▼
  │   Ask user   Block + tell
  │   via WS     employee why
  │     │
  │   ┌─┴──┐
  │   ↓    ↓
  │  yes   no
  │   │    │
  ▼   ▼    ▼
Execute  Block
```

---

## 7. API Endpoints — New & Modified

### 7.1 Employee CRUD

```
POST   /api/employees                    Create employee
GET    /api/employees                    List user's employees
GET    /api/employees/:id                Get employee details
PATCH  /api/employees/:id                Update employee (name, role, persona, config)
DELETE /api/employees/:id                Archive employee (soft delete, preserve memories)
```

### 7.2 Employee Sessions

```
POST   /api/employees/:id/sessions       Start new session (or resume latest)
GET    /api/employees/:id/sessions       List sessions
GET    /api/sessions/:id                 Get session with messages
POST   /api/sessions/:id/messages        Send message to employee
WS     /api/employees/:id/ws             WebSocket for real-time employee interaction
```

### 7.3 Employee Memory

```
GET    /api/employees/:id/memories       List memories (filter by type, tags)
POST   /api/employees/:id/memories       Manually add memory
PATCH  /api/memories/:id                 Update memory (confidence, content)
DELETE /api/memories/:id                 Deactivate memory
POST   /api/employees/:id/memories/consolidate   Trigger consolidation (V1b)
```

### 7.4 Employee Tools & Permissions

```
GET    /api/employees/:id/permissions    Get permission matrix
PATCH  /api/employees/:id/permissions    Update permissions
GET    /api/employees/:id/skills         List skills (V2)
```

### 7.5 Existing Endpoints — Migration Path

The existing `/api/projects/*` endpoints stay. They become one way an employee interacts with work:

```
V1: User creates project → assigns to employee → employee runs pipeline
    (same flow as today, but employee_id attached to project)

Later: Employee can create projects on its own as part of a task
```

---

## 8. Frontend UX — V1

### 8.1 New Pages

```
/employees                  Employee roster (list of user's AI employees)
/employees/new              Create new employee
/employees/:id              Employee profile + chat interface
/employees/:id/memory       Employee memory browser
/employees/:id/history      Session history
```

### 8.2 Employee Chat Interface (Primary UX)

```
┌──────────────────────────────────────────────────────┐
│ ◀ Employees    Atlas — Senior Software Engineer   ⚙  │
├────────────┬─────────────────────────────────────────┤
│            │                                         │
│ Sessions   │  Atlas                                  │
│            │  "I remember from our last session      │
│ ● Today    │   that you prefer FastAPI. I'll use     │
│ ○ Sep 23   │   that for the auth service."           │
│ ○ Sep 20   │                                         │
│            │  ──────────────────────────────────────  │
│            │                                         │
│ Memory  ▼  │  You:                                   │
│ 12 facts   │  Build the payment webhook handler.     │
│ 3 prefs    │                                         │
│ 1 proc     │  Atlas:                                 │
│            │  On it. I'll need GitHub write access    │
│            │  for this — approve?  [Allow] [Deny]    │
│ Tools   ▼  │                                         │
│ GitHub  ✓  │  ┌─────────────────────────────────┐    │
│ E2B     ✓  │  │ █████████░░░░ Building...       │    │
│ Terminal ⚠ │  └─────────────────────────────────┘    │
│            │                                         │
│            │  [Type a message...]            [Send]  │
└────────────┴─────────────────────────────────────────┘
```

### 8.3 What Changes vs Current UI

| Current | V1 |
|---|---|
| Dashboard shows projects list | Dashboard shows employee roster + recent activity |
| Click project → see pipeline | Click employee → see chat + sessions |
| "Start Project" button | Message employee: "Build X" → employee decides pipeline route |
| No memory UI | Memory browser per employee |
| No session continuity | Session list with "continue where we left off" |

The existing project view (Pipeline, AgentOutput, CodePreview, etc.) stays — it's now embedded as a panel within the employee's workspace when they're running a build.

---

## 9. Implementation Phases

### V1a — Persistent Identity + Chat (3 weeks)

**Backend:**
- [ ] `employees` table + CRUD endpoints
- [ ] `employee_sessions` + `session_messages` tables + endpoints
- [ ] Employee chat endpoint: receives message → loads identity + session history → calls LLM → stores response
- [ ] Wire existing pipeline as a tool the employee can invoke ("build project" intent detection)
- [ ] Basic memory: explicit "remember" / "forget" commands → `memories` table (keyword retrieval only)
- [ ] `tool_permissions` table + permission check middleware

**Frontend:**
- [ ] `/employees` roster page
- [ ] `/employees/new` creation form
- [ ] `/employees/:id` chat interface (WebSocket-based)
- [ ] Session sidebar (list + resume)
- [ ] Permission approval dialog (inline in chat)

**What ships:** User can create an employee, chat with it, tell it to build a project (triggers existing pipeline), and the employee remembers what they explicitly tell it to remember.

### V1b — Smart Memory (2 weeks after V1a)

- [ ] Automatic memory extraction on session end
- [ ] Memory type classification (LLM-based)
- [ ] pgvector extension for embedding-based retrieval
- [ ] Hybrid retrieval (SQL filter + vector similarity)
- [ ] Freshness tracking + stale memory warnings
- [ ] Memory browser UI (`/employees/:id/memory`)

### V2 — Skills + Routines (4 weeks after V1b)

- [ ] `skills` table + CRUD
- [ ] Skill execution engine (parse steps, run tools, validate)
- [ ] Routine scheduler (cron-based skill execution)
- [ ] Skill suggestion: "I noticed you do X repeatedly — save as skill?"

### V3 — Multi-Employee (4 weeks after V2)

- [ ] Employee-to-employee messaging (Redis pub/sub)
- [ ] Task delegation ("Atlas assigns QA task to Nova")
- [ ] Shared project workspace
- [ ] Chief of Staff orchestration layer

---

## 10. Migration Strategy

**No breaking changes to existing functionality.** The current app continues to work as-is.

Phase 1: Add employee tables + endpoints alongside existing ones.
Phase 2: Create a "default employee" for each user, mapped to their existing projects.
Phase 3: New frontend routes coexist with old ones. Feature flag toggles between "project-first" and "employee-first" UX.
Phase 4: Once employee UX is validated, make it the default. Old project-only routes become legacy.

---

## 11. Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Vector store | pgvector (PostgreSQL extension) | Already on PostgreSQL (Railway). No new infrastructure. Good enough for <100K memories. |
| Memory embedding model | Claude embedding or OpenAI ada-002 | Evaluated at V1b time. Only needed for semantic retrieval. |
| Employee chat LLM | Same multi-provider chain (engine.py) | Already have Groq→NVIDIA→OpenRouter fallback. Employee config can override model preference. |
| Session storage | PostgreSQL (session_messages) | Need durability across sessions. Redis is for ephemeral state only. |
| Artifact versioning | Defer to V2 | Local artifact store is fine for V1. S3 + versioning added when cloud storage is needed. |
| Skill definition format | JSON (steps + validation + approval_rules) | Simple, extensible, LLM-parseable. Not YAML — harder to validate. |

---

## 12. Open Questions

1. **Employee-per-role or configurable?** Should users create "Atlas the Engineer" with a fixed role, or should employees be role-fluid ("Atlas, today you're doing QA")?
   - Recommendation: Fixed role at creation, but skills make them flexible. An engineer can learn QA skills.

2. **Memory sharing between employees?** If Atlas learns "we use FastAPI", should Nova also know?
   - Recommendation: No for V1. Per-employee memories. V3 introduces shared organizational memory.

3. **Billing model?** Memory storage + LLM calls + E2B time all cost money.
   - Recommendation: Track cost_per_employee via existing cost_tracking table. Surface in UI. Quotas per tier.

4. **Conversation vs task mode?** Sometimes users want to chat ("explain this code"). Sometimes they want action ("fix this bug").
   - Recommendation: Single interface. Employee infers intent. Chat messages that are tasks trigger tool use automatically.
