# Budget & Costs

The AI Software Company runs an entire 6-agent pipeline for **$0.26 per run**. This page breaks down every cost, explains the budget strategy, and projects how far each budget level goes.

## Per-Run Cost Breakdown

> [!status] Total: $0.26 per pipeline run
> | Component | Model / Service | Cost |
> |-----------|----------------|------|
> | CEO Agent | Gemma 4 31B (free) | $0.00 |
> | Business Analyst | Gemma 4 31B (free) | $0.00 |
> | Researcher Agent | Gemma 4 31B (free) | $0.00 |
> | Architect Agent | DeepSeek V3 (free) | $0.00 |
> | **Engineer Agent** | **Claude Sonnet 4** | **~$0.25** |
> | PPT Agent | Gemma 4 31B (free) | $0.00 |
> | Cross-Reviews (4x) | Gemma 4 31B (free) | $0.00 |
> | Tavily Search (2-4 queries) | Tavily API | ~$0.01 |
> | **Pipeline Total** | | **~$0.26** |

## Why Only One Paid Agent?

> [!decision] The Split Strategy
> Only the [[Engineer Agent]] uses a paid model (Claude Sonnet 4). Every other agent does structured extraction, summarization, or review — tasks where free models perform identically to paid ones.
>
> The Engineer is different because it generates 10-16K tokens of **runnable code**. Code quality is the product. No free model matches Claude Sonnet 4 for multi-file code generation.
>
> See [[Model Strategy]] for the full analysis and [[Six Agent Architecture]] for why each role is separate.

## Budget Projections

| Budget | Pipeline Runs | Enough For |
|--------|--------------|------------|
| **$1** | ~3 runs | Quick testing |
| **$5** | ~19 runs | Development + hackathon |
| **$10** | ~38 runs | Comfortable margin for iteration |
| **$20** | ~76 runs | Extended use, post-hackathon |
| **$50** | ~192 runs | Multi-month usage |

> [!pipeline] Hackathon Budget
> For [[SIH Context|SIH 2026]] (Aug 18-19), a **$10 budget** gives 38 pipeline runs. During the 36-hour hackathon, you realistically need 5-10 runs (one per problem statement you explore, plus iterations). $10 is more than enough.

## Billing Infrastructure

| Component | Details |
|-----------|---------|
| **LLM billing** | OpenRouter (pay-per-token, no subscription) |
| **Payment method** | Credit card on OpenRouter account |
| **Free models** | Gemma 4 31B, DeepSeek V3 — genuinely $0.00 on OpenRouter |
| **Paid model** | Claude Sonnet 4 — billed through OpenRouter at Anthropic rates |
| **Search billing** | Tavily API (free tier: 1000 searches/month, paid: $0.005/search) |
| **Routing** | [[OmniRoute Setup|OmniRoute]] at localhost:20128 for local caching and fallbacks |

## Cost Comparison

How does $0.26/run compare to alternatives?

| Approach | Cost per Project | Time | Quality |
|----------|-----------------|------|---------|
| **Our pipeline** | $0.26 | 5-8 min | Good MVP |
| ChatGPT Pro ($20/mo) | ~$0.67 (30 projects/mo) | 30-60 min manual | Inconsistent |
| Freelance developer | $200-500 | 1-2 weeks | High but slow |
| Manual coding | $0 (time cost) | 2-7 days | Depends on skill |

## Cost History

> [!decision] Cost Evolution
> | Phase | Model | Cost/Run | Why Changed |
> |-------|-------|----------|-------------|
> | v0.1 | All Nemotron 550B | ~$0.00 | Free but 400s+ per agent, unusable |
> | v0.2 | All Nemotron 120B | ~$0.00 | Free but queue times killed speed |
> | v0.3 | Split strategy | ~$0.26 | Fast + high quality where it matters |
>
> See [[Model Selection History]] for the full timeline.

## Tavily Search Costs

The [[Researcher Agent]] uses [[Tavily Integration|Tavily Search API]]:

| Tavily Plan | Searches/Month | Cost |
|-------------|---------------|------|
| Free tier | 1,000 | $0.00 |
| Paid | Unlimited | $0.005/search |

Each pipeline run uses 2-4 searches (~$0.01). On the free tier, 1000 searches = ~250-500 pipeline runs — more than enough for development and the hackathon.

---

Related: [[Model Strategy]], [[Engineer Agent]], [[SIH Context]], [[Tech Stack]], [[Model Selection History]], [[Tavily Integration]]

#project #budget #costs
