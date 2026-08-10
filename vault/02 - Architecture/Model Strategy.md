# Model Strategy

The AI Software Company uses a **split model strategy** — expensive paid models only where output quality is critical, free models everywhere else. This keeps cost per pipeline run under $0.30 while maintaining high-quality code generation.

## Agent Model Assignments

| Agent | Recommended Model | Cost | Why |
|-------|-------------------|------|-----|
| **CEO** | Gemma 4 31B | Free | Simple task: extract project brief from problem statement. Free model handles it fine. |
| **Business Analyst** | Gemma 4 31B | Free | Requirements extraction is structured and rule-based. |
| **Researcher** | Gemma 4 31B | Free | Web search + summarization. The web search (Tavily) does the heavy lifting. |
| **Architect** | DeepSeek V3 | Free | Technical spec generation requires reasoning. DeepSeek V3 is strong at structured technical output and free on OpenRouter. |
| **Engineer** | Claude Sonnet 4 | ~$0.25/run | THE critical agent. Generates 16K tokens of runnable code. Quality here = project quality. Worth paying for. |
| **PPT Agent** | Gemma 4 31B | Free | Slide content is derived from prior outputs. Structured extraction. |
| **Cross-Reviews** | Gemma 4 31B | Free | Reviews compare output against requirements. Pattern matching, not generation. |

## Cost Analysis

> [!status] Per-Run Cost Breakdown
> | Component | Cost |
> |-----------|------|
> | CEO (Gemma 4 31B) | $0.00 |
> | Business Analyst (Gemma 4 31B) | $0.00 |
> | Researcher (Gemma 4 31B) | $0.00 |
> | Architect (DeepSeek V3) | $0.00 |
> | **Engineer (Claude Sonnet 4)** | **~$0.25** |
> | PPT Agent (Gemma 4 31B) | $0.00 |
> | Cross-Reviews (5x Gemma 4 31B) | $0.00 |
> | Tavily Search (Researcher) | ~$0.01 |
> | **Total per pipeline run** | **~$0.26** |

## Budget Projections

> [!decision] Budget: $5-10
> | Budget | Full Pipeline Runs | Notes |
> |--------|-------------------|-------|
> | $5 | ~19 runs | Enough for development + hackathon |
> | $10 | ~38 runs | Comfortable margin, can iterate |
> | $20 | ~76 runs | Overkill for hackathon, good for post-event |

## Why This Split?

> [!agent] The Key Insight
> Only **one agent** (Engineer) generates content where quality directly determines the final product. All other agents do structured extraction, summarization, or review — tasks where free models perform well.

### DeepSeek V3 for Architect

The Architect agent generates technical specifications — framework choices, file structures, API designs. DeepSeek V3 excels at this because:
- Strong at structured reasoning and technical planning
- Outputs well-organized JSON consistently
- Free on OpenRouter (0217 snapshot)
- Handles the "think before you build" task better than simpler models

### Claude Sonnet 4 for Engineer

The Engineer is the only agent where you should **never** use a free model:
- Generates 10-16K tokens of actual, runnable code
- Must handle complex file structures (multiple files, imports, configs)
- Code quality = project quality — there is no downstream fix
- Claude Sonnet 4 has the best code generation among available models
- At ~$0.25/run, the ROI is massive (you get a complete project)

### Free Models for Everything Else

CEO, BA, Researcher, PPT, and cross-reviews all do one of:
- **Extraction**: Pull structured data from unstructured input
- **Summarization**: Condense information into a format
- **Comparison**: Check one output against requirements
- **Transformation**: Convert one structured format to another

These tasks do not require frontier model intelligence. Gemma 4 31B handles them reliably at zero cost.

## Configuration

Model assignments are configured in `backend/app/core/config.py` via the `MODEL_CONFIG` dictionary, and routed through [[OmniRoute Setup]] at `localhost:20128`.

---

Related: [[Tech Stack]], [[OmniRoute Setup]], [[Agent Roster]], [[Orchestrator]]

#architecture #models #cost
