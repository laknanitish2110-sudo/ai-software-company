# CEO Agent

The CEO is the **first agent** in the pipeline. It takes the founder's raw problem statement and produces a structured project brief that guides all downstream agents.

## Role

> [!agent] Chief Executive Officer
> **Mission:** Transform a vague problem statement into a clear, actionable project brief.
>
> The CEO must extrapolate from minimal input. In SIH hackathons, problem statements can be as short as 11 characters (e.g., "Smart waste management"). The CEO fills in the gaps — target users, core features, success metrics, and project scope.

## Pipeline Position

```mermaid
graph LR
    F["Founder"] -->|problem statement| CEO["CEO ★"]
    CEO -->|project brief| BA["Business Analyst"]
    style CEO fill:#f5a623,stroke:#f5a623,color:#0f0f14
```

**Position:** 1st of 6 agents
**Approval Gate:** None (auto-approved)
**Reviews:** [[Agent Roster|Business Analyst]] output (cross-review)

## Input

| Field | Details |
|-------|---------|
| **Source** | Founder (user) |
| **Format** | Plain text string |
| **Min length** | Can be as short as 11 characters |
| **Max length** | No hard limit, but typically 1-3 sentences |
| **Context** | SIH problem statements: 498 options, 15 themes, govt orgs |

## Output

The CEO produces a **project brief JSON** with 8 fields:

| Field | Description |
|-------|-------------|
| `project_name` | Clear, descriptive name for the project |
| `problem_summary` | Expanded version of the problem statement |
| `target_users` | Who will use the final product |
| `core_features` | 4-6 key features the product must have |
| `tech_suggestions` | Recommended technologies (frontend, backend, APIs) |
| `success_metrics` | How to measure if the project works |
| `scope` | What's in scope for a hackathon MVP |
| `risks` | Potential challenges and mitigations |

## Model

> [!decision] Model Choice
> | Setting | Value |
> |---------|-------|
> | **Recommended** | Gemma 4 31B |
> | **Cost** | Free (via OpenRouter) |
> | **Why free?** | The CEO task is structured extraction + extrapolation. Free models handle this reliably. |
> | **Alternative** | Any instruction-following model works here |

See [[Model Strategy]] for the full cost analysis.

## Performance

| Metric | Value |
|--------|-------|
| **Average time** | ~30s (with fast model) |
| **Test run time** | 96s (with Nemotron 120B) |
| **Token output** | ~500-800 tokens |
| **Failure rate** | Very low — simplest agent task |

## Key Files

- **Prompt:** `backend/app/agents/prompts.py` (CEO system prompt)
- **Execution:** `backend/app/agents/engine.py` (agent runner)
- **Orchestrator call:** `backend/app/services/orchestrator.py`

---

Related: [[Agent Roster]], [[Orchestrator]], [[Model Strategy]], [[Pipeline Test Results]]

#agent #ceo
