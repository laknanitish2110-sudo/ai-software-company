# Cross Review System

## What Is It

After each agent finishes their work (but BEFORE the Founder sees it), a teammate reviews their output — like a real team standup where someone speaks up about a colleague's work.

**File:** `backend/app/agents/engine.py` — `cross_review()` function

## Review Matrix

| Agent Finishes | Reviewed By | Why This Reviewer |
|----------------|-------------|-------------------|
| Business Analyst | CEO | Does the analysis match my project brief? |
| Researcher | Business Analyst | Does the research cover our requirements? |
| Architect | Researcher | Are the tech choices supported by my research? |
| Engineer | Architect | Does the code follow my architecture? |

Each review = 1 LLM call (max 1024 tokens). 4 reviews across the full pipeline.

## What the Reviewer Produces

```json
{
  "reviewer": "ceo",
  "reviewer_label": "CEO / Project Manager",
  "reviewed": "business_analyst",
  "overall_assessment": "1-2 sentence summary",
  "strengths": ["what they did well"],
  "concerns": ["issues spotted"],
  "suggestions": ["improvements to consider"],
  "team_note": "A brief message to the Founder, as if speaking in a team meeting"
}
```

## How It Shows Up

In the dashboard, each agent's output card includes a **Peer Review** section:
- The reviewer's team note (quoted, like a standup comment)
- Overall assessment
- Strengths (green, with + prefix)
- Concerns (amber, with ! prefix)
- Suggestions (cyan, with ~ prefix)

The Founder sees: the agent's work + a teammate's opinion BEFORE deciding to approve or reject.

## Pipeline Flow

```
Agent finishes work
  ↓
cross_review() runs (reviewer agent called)
  ↓
Review stored in shared_memory (key: peer_review_{role})
  ↓
WebSocket: "peer_review_completed" event
  ↓
Status → review (Founder sees output + review)
  ↓
Founder approves/rejects
```

## Design Decisions

1. **One reviewer per agent** — keeps it fast (1 extra LLM call, not 3-4). The most relevant teammate reviews.
2. **Runs before Founder sees it** — the discussion happens first, then the Founder gets the enriched view.
3. **Non-blocking on failure** — if the review LLM call fails, the pipeline continues normally without the review.
4. **Stored in shared memory** — uses existing infrastructure, no new database tables.
5. **Output truncated at 8000 chars** — prevents massive Engineer outputs from blowing up review context.

Related: [[Agent Roster]], [[Orchestrator]], [[How It Works]]
