# Six Agent Architecture

The most important design decision in the entire project: **six separate agents, each with a single role, never consolidated**. This page documents the reasoning, the alternatives considered, and why separation IS the value.

## The Decision

> [!decision] Never Consolidate Roles
> Each agent thinks differently about the same problem. A Business Analyst focuses on requirements. A Researcher focuses on what exists. An Architect focuses on how to build. Merging any two of these loses the focused perspective that makes each output valuable.
>
> **Rule:** If someone suggests combining agents to "simplify" the pipeline, the answer is no. Separation is not a bug — it is the product.

## The Six Roles

| Agent | Thinking Mode | Unique Contribution |
|-------|--------------|---------------------|
| [[CEO Agent]] | Strategic | Turns vague input into structured direction |
| [[Business Analyst Agent]] | Analytical | Requirements, scope, acceptance criteria |
| [[Researcher Agent]] | Investigative | Real-world context, competitors, data |
| [[Architect Agent]] | Structural | Technical blueprint, file structure, trade-offs |
| [[Engineer Agent]] | Generative | Actual runnable code |
| [[PPT Agent]] | Narrative | Story that ties everything together |

## Why Not Fewer Agents?

### "Just combine CEO + BA"

> [!decision] Rejected: CEO + BA Merge
> **Argument:** "The CEO already produces a brief with features. The BA just expands it. Merge them."
>
> **Counter:** The CEO thinks like a founder — broad strokes, vision, scope. The BA thinks like a product manager — detailed requirements, edge cases, acceptance criteria. These are fundamentally different cognitive modes. When one model tries to do both, it either gives a shallow brief OR detailed requirements, never both at the quality level you get from two focused passes.

### "Just combine Researcher + BA"

> [!decision] Rejected: Researcher + BA Merge
> **Argument:** "The BA could just search the web while writing requirements."
>
> **Counter:** Research is exploratory. Requirements are definitive. Combining them means the model either under-researches (skips web search to focus on requirements) or over-specifies (lets search results dictate requirements instead of informing them). Separation means research is thorough AND requirements are independent.

### "Just combine Architect + Engineer"

> [!decision] Rejected: Architect + Engineer Merge
> **Argument:** "The Engineer could design the architecture while coding."
>
> **Counter:** This is the most tempting merge and the worst idea. Without a separate architecture step:
> - The Engineer starts coding before thinking about structure
> - File organization is inconsistent
> - No trade-off documentation
> - No clear API design before implementation
> - The [[Cross Review System]] loses the Architect→Engineer review (most valuable review in the pipeline)

### "Just use one big agent"

> [!decision] Rejected: Single Agent
> **Argument:** "Give Claude Sonnet 4 the problem statement and ask it to produce everything."
>
> **Counter:** This is literally what ChatGPT does. And it produces generic, surface-level output. The entire value proposition of this project is that **specialized agents produce better results than a generalist**. One agent cannot maintain the focused thinking required for 6 different cognitive tasks in a single generation.

## The Quality Math

Each agent adds signal that the next agent builds on:

```
CEO brief → 8 structured fields from 1-2 sentences
  + BA requirements → 8 MORE fields (user stories, scope, criteria)
    + Research → 8 MORE fields (competitors, data, APIs)
      + Architecture → 8 MORE fields (file structure, DB, trade-offs)
        = Engineer receives ~32 structured fields of context
```

A single agent working from the raw problem statement gets: 1-2 sentences of context. The [[Engineer Agent]] working through the pipeline gets: 32+ structured fields. The difference in output quality is dramatic.

## Cross-Review Reinforcement

The [[Cross Review System]] only works because agents are separate. Each reviewer checks the downstream agent's work against their own expertise:

| Reviewer | Reviews | Looking For |
|----------|---------|-------------|
| CEO | BA | "Does this match my vision?" |
| BA | Researcher | "Does research cover my requirements?" |
| Researcher | Architect | "Are tech choices backed by data?" |
| Architect | Engineer | "Does code follow my design?" |

If agents were merged, there would be no independent reviewer. The [[Approval Gate Design|approval gates]] + cross-reviews create quality control that consolidation destroys.

## Performance vs. Separation

> [!pipeline] The Trade-off
> | Metric | 1 Agent | 6 Agents |
> |--------|---------|----------|
> | Speed | ~2 min | ~5-8 min |
> | Cost | ~$0.25 | ~$0.26 |
> | Output fields | ~10 | ~50+ |
> | Quality control | None | 4 gates + 4 reviews |
> | Iteration | Start over entirely | Fix just the failing agent |
>
> The 6-agent approach costs $0.01 more and takes 3-6 minutes longer, but produces dramatically more thorough output with built-in quality control.

---

Related: [[Agent Roster]], [[Cross Review System]], [[Model Strategy]], [[How It Works]], [[Approval Gate Design]], [[Project Vision]]

#decision #architecture #core-philosophy
