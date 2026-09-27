# Jev Decision Layer

> **Cheap model for routing and QA, expensive model for creative work. Inspired by DeepSeek's MoE insight.**

## The Insight

Most AI decisions don't need an expensive model:
- "Is this output complete?" → cheap model
- "Does this code have syntax errors?" → cheap model
- "Write a production-ready authentication system" → expensive model

Jev routes the right query to the right model, cutting costs ~60% without quality loss.

## Implementation

### Model Routing

| Role | Model | Provider | Purpose |
|------|-------|----------|---------|
| `jev` | Lightning 30B | Groq (fast) / NVIDIA (fallback) | Routing, QA triage, structural checks |
| `qa` | Super 120B | NVIDIA | Deep quality review, domain expert review |
| `engineer` | Claude/DeepSeek | NVIDIA/Groq | Creative code generation |
| `architect` | DeepSeek V3 | NVIDIA | System design |
| Other roles | Gemma/Nemotron | Various | Analysis, research, writing |

### Where Jev Is Used

1. **Sentinel Tier 1** — structural verification uses `llm_role="jev"` (cheap)
2. **Sentinel Tiers 2-3** — deep/domain review uses `llm_role="qa"` (standard)
3. **Future: Goal triage** — classify goal difficulty before assigning employee
4. **Future: Retry decisions** — should we retry or escalate?

### Config

```python
# backend/app/core/config.py
PROVIDER_MAP = {
    "jev": "groq" if GROQ_API_KEY else "nvidia2",
    "qa": "nvidia",
    # ... other roles
}
MODEL_MAP = {
    "jev": "nvidia/nemotron-3.5-lightning-30b-a3b",  # Cheapest
    "qa": "nvidia/nemotron-3-super-120b-a12b",       # Strongest
}
```

All 4 config maps populated: MODEL_MAP, PROVIDER_MAP, FALLBACK_MAP, FALLBACK_PROVIDER_MAP.

## Cost Impact

| Scenario | Without Jev | With Jev | Savings |
|----------|------------|---------|---------|
| Sentinel QA (Tier 1) | Super 120B ($X) | Lightning 30B ($0.05X) | ~95% |
| 100 executions/day | 100 × full cost | 60 caught at Tier 1, 40 go to Tier 2 | ~50-60% |

---

Related: [[Multi-Tier Sentinel]], [[Core Thesis]], [[Model Strategy]]

#jev #cost #routing
