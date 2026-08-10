# Pipeline Flow

The complete data flow from a raw problem statement to a finished software project with deliverables. Every piece of data is traceable — you can see exactly what each agent received, what it produced, and how long it took.

## End-to-End Flow

```mermaid
graph TD
    PS["Problem Statement"] -->|"raw text (11-200 chars)"| CEO
    CEO["CEO Agent"] -->|project brief JSON| BA
    BA["Business Analyst"] -->|requirements JSON| G1{"Gate 1"}
    G1 -->|approved| RES["Researcher"]
    G1 -->|rejected + feedback| BA
    RES -->|research report JSON| G2{"Gate 2"}
    G2 -->|approved| ARCH["Architect"]
    G2 -->|rejected + feedback| RES
    ARCH -->|technical spec JSON| G3{"Gate 3"}
    G3 -->|approved| ENG["Engineer"]
    G3 -->|rejected + feedback| ARCH
    ENG -->|code JSON (16K tokens)| G4{"Gate 4"}
    G4 -->|approved| PPT["PPT Agent"]
    G4 -->|rejected + feedback| ENG
    PPT -->|slide content JSON| GEN["File Generators"]
    GEN -->|".zip + .pptx + .docx"| DEL["Deliverables"]

    style G1 fill:#f39c12,stroke:#f39c12,color:#fff
    style G2 fill:#f39c12,stroke:#f39c12,color:#fff
    style G3 fill:#f39c12,stroke:#f39c12,color:#fff
    style G4 fill:#f39c12,stroke:#f39c12,color:#fff
```

## Agent Data Contract

Each agent receives all previously approved outputs via **shared memory**. Here is exactly what flows between agents:

| Agent | Receives | Produces | Output Size |
|-------|----------|----------|-------------|
| [[CEO Agent]] | Problem statement (raw text) | Project brief (8 fields) | ~500-800 tokens |
| [[Business Analyst Agent]] | CEO brief | Requirements doc (8 fields) | ~800-1200 tokens |
| [[Researcher Agent]] | CEO brief + BA requirements | Research report (8 fields) + sources | ~1000-1500 tokens |
| [[Architect Agent]] | CEO + BA + Research | Technical spec (8 fields) | ~1500-2500 tokens |
| [[Engineer Agent]] | CEO + BA + Research + Architecture | Complete codebase as JSON | ~10,000-16,000 tokens |
| [[PPT Agent]] | All 5 previous outputs | Slide content (10 slides) | ~1000-1500 tokens |

> [!pipeline] Context Accumulation
> Each agent sees MORE context than the last. The Engineer receives the most — all 4 previous outputs. This is why the Engineer's prompt is the most expensive (largest input + largest output). The [[Model Strategy]] accounts for this.

## Timing Data (Test Run)

From the first full pipeline test with Nemotron 120B models:

| Agent | Time | Cumulative | Notes |
|-------|------|------------|-------|
| **CEO** | 96s | 96s | Includes model queue time |
| **Business Analyst** | 125s | 221s | Longest analysis agent |
| **Researcher** | 141s | 362s | Includes Tavily API calls |
| **Architect** | 5s | 367s | Fastest — DeepSeek V3 is quick |
| **Engineer** | 400s+ | 767s+ | Longest — generates full codebase |
| **PPT** | ~30s | ~800s | Estimates (not in original test) |
| **Total** | — | **~13 min** | With Nemotron 120B |

> [!status] Speed After Model Switch
> After switching to the current [[Model Strategy]] (Gemma 4 31B + Claude Sonnet 4), total pipeline time dropped significantly. The Nemotron models had queue times of 30-60s per call. Current estimates are 5-8 minutes end-to-end. See [[Model Selection History]] for the full timeline.

## Shared Memory Structure

All inter-agent communication goes through a shared memory dictionary, stored in the database:

```
shared_memory = {
    "problem_statement": "original input",
    "ceo_brief": { ... },
    "ba_requirements": { ... },
    "research_report": { ... },
    "architect_spec": { ... },
    "engineer_code": { ... },
    "ppt_content": { ... },
    "peer_review_business_analyst": { ... },
    "peer_review_researcher": { ... },
    "peer_review_architect": { ... },
    "peer_review_engineer": { ... },
    "revision_feedback_business_analyst": "...",
    ...
}
```

See [[Database Schema]] for how this is persisted and [[Orchestrator]] for how shared memory is managed.

## Cross-Review Overlay

Between each agent's completion and the Founder's approval decision, a [[Cross Review System|cross-review]] runs:

```
Agent completes → Cross-review runs → Founder sees output + review → Approve/Reject
```

| Agent Output | Reviewed By | Review Question |
|--------------|-------------|-----------------|
| BA requirements | CEO | "Does this match my project brief?" |
| Research report | BA | "Does this cover our requirements?" |
| Technical spec | Researcher | "Are tech choices supported by research?" |
| Engineer code | Architect | "Does code follow my architecture?" |

## Webhook Events

At each pipeline stage, [[Webhook System|webhook events]] fire to [[n8n Integration|n8n]]:

| Stage | Event Type | Payload |
|-------|-----------|---------|
| Agent starts | `agent_started` | agent role, project ID |
| Agent finishes | `agent_completed` | agent role, output summary |
| Gate reached | `approval_needed` | agent role, output for review |
| Pipeline complete | `deliverables_ready` | download URLs |
| Any failure | `error` | error details, agent role |

---

Related: [[How It Works]], [[Orchestrator]], [[Agent Roster]], [[Cross Review System]], [[Webhook System]], [[Model Strategy]]

#architecture #pipeline #data-flow
