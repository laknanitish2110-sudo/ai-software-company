# Model Strategy

The AI Software Company uses a **100% free model strategy** via OpenRouter — every agent runs on a free-tier model, keeping cost per pipeline run at **$0.00**. Models are assigned by capability match: fast lightweight models for simple tasks, strong reasoning models for complex analysis, and coding-focused models for code generation.

## Agent Model Assignments

| Agent | Model | Parameters | Why |
|-------|-------|------------|-----|
| **CEO** | Nemotron 3.5 Lightning | 30B MoE | Fast, concise briefs — lightweight extraction |
| **Business Analyst** | Nemotron 3 Super | 120B MoE | Structured requirements need strong reasoning |
| **Researcher** | Nemotron 3 Super | 120B MoE | Web search synthesis requires comprehension |
| **Architect** | Nemotron 3 Super | 120B MoE | Technical spec generation requires reasoning |
| **Engineer** | North Mini Code | Coding-focused | Best free coding model — specialized for code gen |
| **PPT Agent** | Nemotron 3.5 Lightning | 30B MoE | Slide content is derived, lightweight task |
| **Cross-Reviews** | Nemotron 3.5 Lightning | 30B MoE | Short evaluations, pattern matching |

## Cost Analysis

> [!status] Per-Run Cost Breakdown
> | Component | Cost |
> |-----------|------|
> | CEO (Nemotron 3.5 Lightning) | $0.00 |
> | Business Analyst (Nemotron 3 Super) | $0.00 |
> | Researcher (Nemotron 3 Super) | $0.00 |
> | Architect (Nemotron 3 Super) | $0.00 |
> | Engineer (North Mini Code) | $0.00 |
> | PPT Agent (Nemotron 3.5 Lightning) | $0.00 |
> | Cross-Reviews (Nemotron 3.5 Lightning) | $0.00 |
> | Tavily Search (Researcher) | ~$0.01 |
> | **Total per pipeline run** | **~$0.01** |

## Model Tiers

### Tier 1: Fast (Nemotron 3.5 Lightning — 30B MoE)
- **Agents:** CEO, PPT, Cross-Reviews
- **Why:** These agents do structured extraction, content derivation, or short evaluations. Speed matters more than depth. 1M context window handles any input.

### Tier 2: Strong (Nemotron 3 Super — 120B MoE)
- **Agents:** BA, Researcher, Architect
- **Why:** Requirements analysis, research synthesis, and technical design need reasoning capability. 120B MoE balances quality and speed on the free tier.

### Tier 3: Code (Cohere North Mini Code)
- **Agents:** Engineer
- **Why:** Purpose-built for code generation. Specialized coding model produces better code than general-purpose models of similar size. 256K context handles large codebases.

## Rate Limit Handling

Free-tier models on OpenRouter can hit rate limits (429 errors). The system handles this with:
- **Retry with backoff:** 429 errors retry with 3x longer delays (6s, 12s, 24s)
- **Fallback model:** If primary model fails, falls back to Nemotron 3.5 Lightning
- **Provider diversity:** Models spread across NVIDIA, Cohere, and MiniMax to avoid shared rate limits

## Configuration

Model assignments are configured via environment variables in `backend/.env`:
```
MODEL_CEO=nvidia/nemotron-3.5-lightning:free
MODEL_BA=nvidia/nemotron-3-super-120b-a12b:free
MODEL_RESEARCHER=nvidia/nemotron-3-super-120b-a12b:free
MODEL_ARCHITECT=nvidia/nemotron-3-super-120b-a12b:free
MODEL_ENGINEER=cohere/north-mini-code:free
MODEL_PPT=nvidia/nemotron-3.5-lightning:free
MODEL_REVIEW=nvidia/nemotron-3.5-lightning:free
```

---

Related: [[Tech Stack]], [[Agent Roster]], [[Orchestrator]], [[Model Selection History]]

#architecture #models #cost
