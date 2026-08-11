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
| PPT | Engineer | Does the presentation match the actual implementation? |

Each review = 1 LLM call (max 1024 tokens). 5 reviews across the full pipeline.

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
  "team_note": "A brief message to the Founder, as if speaking in a team meeting",
  "quality_score": 8,
  "alignment_check": "How well this output aligns with upstream deliverables",
  "hackathon_readiness": "Whether this is demo-ready for a 24-hour hackathon"
}
```

### Quality Score

A 1-10 rating displayed as a color-coded badge on the frontend:
- **8-10** (green) — Production-ready, strong output
- **6-7** (blue) — Good, minor improvements possible
- **4-5** (yellow) — Needs work, significant gaps
- **1-3** (red) — Major issues, likely needs rejection

### Role-Specific Review Criteria

Each reviewer evaluates against 5 role-specific questions defined in `REVIEW_CRITERIA` (in `prompts.py`):

| Role Reviewed | Example Criteria |
|---------------|-----------------|
| Business Analyst | Are personas Indian-specific? Is scope realistic for 24h? |
| Researcher | Are sources credible and Indian-relevant? Prior SIH winners cited? |
| Architect | Is the stack deployable in 3 commands? Does it handle 2G connectivity? |
| Engineer | Does code run with `npm start` / `python app.py`? Indian locale data? |
| PPT | Does it follow SIH judge criteria? Real Indian statistics included? |

## How It Shows Up

In the dashboard, each agent's output card includes a **Peer Review** section:
- **Quality Score badge** (color-coded 1-10 rating)
- The reviewer's team note (quoted, like a standup comment)
- Overall assessment
- **Alignment check** — how well the output matches upstream work
- **Hackathon readiness** — whether it's demo-ready
- Strengths (green, with + prefix)
- Concerns (amber, with ! prefix)
- Suggestions (cyan, with ~ prefix)

The Founder sees: the agent's work + a teammate's opinion + a quality score BEFORE deciding to approve or reject.

## Pipeline Flow

```
Agent finishes work
  |
cross_review() runs (reviewer agent called)
  |
Review stored in shared_memory (key: peer_review_{role})
  |
WebSocket: "peer_review_completed" event
  |
Status -> review (Founder sees output + review)
  |
Founder approves/rejects
```

## Design Decisions

1. **One reviewer per agent** — keeps it fast (1 extra LLM call, not 3-4). The most relevant teammate reviews.
2. **Runs before Founder sees it** — the discussion happens first, then the Founder gets the enriched view.
3. **Non-blocking on failure** — if the review LLM call fails, the pipeline continues normally without the review.
4. **Stored in shared memory** — uses existing infrastructure, no new database tables.
5. **Output truncated at 8000 chars** — prevents massive Engineer outputs from blowing up review context.
6. **PPT included** — Engineer reviews PPT to ensure the presentation matches the actual implementation.
7. **Quality score** — gives the Founder a quick at-a-glance assessment without reading the full review.
8. **Role-specific criteria** — reviewers evaluate against checklist questions tailored to the SIH hackathon context.

Related: [[Agent Roster]], [[Orchestrator]], [[How It Works]]
