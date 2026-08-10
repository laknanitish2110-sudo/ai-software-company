# Agent Design Patterns

The 7 patterns every agent developer should know. Real systems layer multiple patterns together.

---

## 1. Tool Use (Function Calling)

> The agent calls external functions, APIs, databases to access real-time information.

```
User: "What's the weather in Hyderabad?"

Agent thinks: I need current weather data → call weather_api("Hyderabad")
Tool returns: { temp: 32°C, humidity: 78%, condition: "Partly cloudy" }
Agent responds: "It's 32°C and partly cloudy in Hyderabad with 78% humidity."
```

**How it works:**
1. LLM decides which tool to call
2. Provides parameters for the tool
3. Interprets the returned results
4. Responds based on real data, not guessing

**Without tool use** — agent operates on probability (hallucination risk)
**With tool use** — agent grounds reasoning in real-time facts

**Production status:** Ready. Low risk.

**Our project uses this:** [[Researcher Agent]] calls Tavily web search. [[Engineer Agent]] generates actual files.

---

## 2. ReAct (Reason + Act)

> Agent alternates between **thinking** and **doing** in iterative cycles.

```
THOUGHT: I need to find competitor products for crop disease detection
ACTION: search("crop disease detection apps India")
OBSERVATION: Found Plantix, CropIn, Google Lens plant ID...
THOUGHT: Now I need to compare their features
ACTION: search("Plantix vs CropIn features pricing")
OBSERVATION: Plantix requires internet, CropIn is enterprise-only...
THOUGHT: I have enough to write the analysis
ACTION: generate_report(competitors_data)
```

**The loop:** Think → Act → Observe → Think → Act → Observe → ... → Done

**When to use:** Tasks where you don't know the full path upfront. The agent discovers the path by doing.

**Caution:** Needs max iteration limits (otherwise infinite loops).

**Production status:** Ready. Medium caution — add guardrails on iterations.

**Our project:** Each agent runs a ReAct-style loop (reason about the problem → generate output → validate JSON).

---

## 3. Reflection (Self-Critique)

> Agent evaluates its own output, identifies problems, and revises.

```
Step 1: Generate initial code
Step 2: Review — "This SQL query has no index hint, will be slow on 1M rows"
Step 3: Revise — Add index, optimize query
Step 4: Review again — "Looks good now"
Step 5: Return final output
```

**How it works:**
1. Agent generates initial output
2. Agent critiques its own work against criteria
3. If critique finds issues → revise and re-evaluate
4. Repeat until quality threshold met

**Quality depends on:** How specific your evaluation criteria are. Vague criteria = vague reflection.

**Production status:** Conditional — needs well-defined quality metrics.

**Our project:** [[Cross Review System]] — agents review each other's work (peer reflection).

---

## 4. Planning (Task Decomposition)

> Agent creates an explicit plan before execution, breaking complex goals into subtasks.

```
GOAL: Build a crop disease detection app

PLAN:
  1. Analyze requirements and user needs
  2. Research existing solutions and datasets
  3. Design system architecture
  4. Implement core detection model
  5. Build mobile app UI
  6. Create presentation for judges

EXECUTE: Run each step sequentially, checking off as completed.
```

**Key insight:** Use a frontier model (expensive) for planning, cheaper models for execution — saves 70-90% on costs.

**Production status:** Conditional — needs plan validation and resumability.

**Our project:** The [[CEO Agent]] creates the master plan. The [[Pipeline Flow|orchestrator]] executes it step by step.

---

## 5. Multi-Agent Collaboration

> Multiple specialized agents with defined roles work together under coordination.

```
┌──────────────┐
│ Orchestrator  │
└──┬───┬───┬───┘
   │   │   │
   ▼   ▼   ▼
 ┌───┐┌───┐┌───┐
 │ R ││ W ││ E │  R = Researcher
 └───┘└───┘└───┘  W = Writer
                   E = Editor
```

**How it works:**
1. Orchestrator decomposes the goal
2. Routes subtasks to specialist agents
3. Agents work independently or hand off to each other
4. Quality checks route failures back for revision
5. Orchestrator aggregates final result

**Caution:** Complex coordination, harder to debug. Only use when a single agent genuinely can't handle the task.

**Our project:** This IS our project — 6 agents collaborating in a [[Pipeline Flow|sequential pipeline]].

---

## 6. Sequential Workflows (Chained Agents)

> Multiple agents chain in defined sequence. Each output becomes the next input.

```
Agent 1 (CEO) → Agent 2 (BA) → Agent 3 (Researcher) → Agent 4 (Architect) → Agent 5 (Engineer) → Agent 6 (PPT)
```

**Characteristics:**
- Predictable, linear flow
- Each step validates before passing to next
- Clear failure points at each node
- Most debuggable pattern

**vs Multi-Agent:** Sequential is a subset — agents don't communicate freely, they pass output forward in a chain.

**Production status:** Ready. Low risk. Most reliable pattern.

**Our project:** Our [[Pipeline Flow]] is sequential with [[Approval Gate Design|approval gates]] between steps.

---

## 7. Human-in-the-Loop (Approval Gates)

> Agent pauses at defined decision points for human review before proceeding.

```
Agent works autonomously...
  ↓
[CHECKPOINT] — Agent pauses
  ↓
Human reviews: ✅ Approve / ❌ Reject with feedback
  ↓
Agent continues (or revises based on feedback)
```

**When to add gates:**
- High-cost actions (deploying code, sending emails)
- Regulated domains (finance, healthcare, legal)
- Brand-published content
- Whenever cost of autonomous mistake > cost of human review

**Our project:** 4 approval gates — after [[Business Analyst Agent|BA]], [[Researcher Agent|Researcher]], [[Architect Agent|Architect]], and [[Engineer Agent|Engineer]].

---

## Pattern Combinations

Real production agents layer multiple patterns:

| System | Patterns Used |
|--------|--------------|
| **Coding agent** (Claude Code) | Tool Use + ReAct + Reflection + Planning |
| **Research agent** (Deep Research) | Planning + Tool Use + ReAct + Reflection |
| **Customer support** | Tool Use + Sequential + Human-in-the-Loop |
| **Our AI Software Company** | Planning + Sequential + Multi-Agent + Tool Use + Human-in-the-Loop + Reflection (cross-review) |

---

See [[Agentic AI - Master Guide]] | [[Multi-Agent Architectures]] | [[Our AI Software Company]]

#agentic-ai #design-patterns #knowledge
