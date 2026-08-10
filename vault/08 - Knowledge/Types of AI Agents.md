# Types of AI Agents

> [!info] Two ways to classify agents
> 1. **By architecture** — How the agent thinks internally (reactive vs deliberative)
> 2. **By capability** — What the agent can do (simple reflex vs learning)

## Classification by Architecture

### 1. Reactive Agents
> Stimulus → Response. No memory, no planning.

- Operates on direct input-output mapping
- Predefined rules: "if X happens, do Y"
- No internal state or history
- Fastest response time, lowest complexity

**Example:** A spam filter that flags emails based on keyword rules.

**Strengths:** Fast, predictable, easy to debug
**Weakness:** Cannot handle novel situations

---

### 2. Deliberative Agents
> Think before acting. Has memory, can plan.

- Maintains an internal model of the world
- Plans multiple steps ahead before acting
- Uses memory to inform decisions
- Can reason about consequences

**Example:** A travel booking agent that compares flights, hotels, and schedules before recommending an itinerary.

**Strengths:** Handles complex tasks, considers context
**Weakness:** Slower, computationally expensive

---

### 3. Hybrid Agents
> Fast reactions + deep thinking when needed.

- Combines reactive (fast) and deliberative (smart) layers
- Reactive layer handles immediate, time-sensitive actions
- Deliberative layer handles complex planning
- Most production agents in 2026 are hybrid

**Example:** A customer service agent that instantly greets users (reactive) but plans multi-step troubleshooting workflows (deliberative).

---

### 4. Autonomous Agents
> Operate with minimal human intervention.

- Perceive, decide, act, and adapt independently
- Set their own sub-goals within defined constraints
- Self-monitor and self-correct
- Human oversight at boundaries, not every step

**Example:** An autonomous coding agent that reads a GitHub issue, writes code, runs tests, and opens a PR.

---

## Classification by Capability (Russell & Norvig)

### 1. Simple Reflex Agents
- Act solely on current input
- No memory of past states
- Uses condition-action rules
- Cannot handle partial observability

```
IF sensor_reading == X → DO action_Y
```

**Example:** A thermostat — if temperature > 75°F, turn on AC.

---

### 2. Model-Based Reflex Agents
- Maintains an internal model of the world
- Tracks things it cannot currently see
- Updates model based on actions and observations
- Still uses condition-action rules but with richer context

**Example:** A self-driving car tracking other vehicles even when temporarily occluded.

---

### 3. Goal-Based Agents
- Has explicit goals to achieve
- Considers future consequences of actions
- Can plan sequences of actions to reach goals
- More flexible than reflex agents

**Example:** A navigation agent that plans a route considering traffic, distance, and road closures.

---

### 4. Utility-Based Agents
- Optimizes for a utility function (not just goals)
- Chooses between actions based on expected "happiness"
- Can handle trade-offs (speed vs cost vs quality)
- Makes decisions under uncertainty

**Example:** A stock trading agent that balances risk vs return vs transaction costs.

---

### 5. Learning Agents
- Improves performance over time
- Has a learning element that modifies behavior based on feedback
- Has a critic that evaluates outcomes
- Can adapt to new environments

**Example:** A recommendation engine that learns user preferences from click patterns.

---

### 6. Hierarchical Agents
- Organized in layers of abstraction
- Higher-level agents set goals and supervise
- Lower-level agents execute specific tasks
- Enables complex organizational structures

**Example:** A project management AI where a CEO agent delegates to BA, Researcher, Architect, Engineer agents (like [[Our AI Software Company]]!)

---

## Classification by Domain

| Domain | What They Do | Examples |
|--------|-------------|----------|
| **Coding Agents** | Write, debug, test, deploy code | Claude Code, Cursor, GitHub Copilot, Devin |
| **Research Agents** | Search, synthesize, report findings | Perplexity, Deep Research, Elicit |
| **Customer Support** | Handle tickets, troubleshoot, escalate | Intercom Fin, Ada, Zendesk AI |
| **Browser Agents** | Navigate web, fill forms, extract data | Browserbase, MultiOn, Playwright agents |
| **Workflow Agents** | Automate business processes | Zapier AI, n8n AI nodes, Make.com |
| **Voice Agents** | Handle phone calls, transcribe, respond | ElevenLabs, Vapi, Bland AI |
| **Data Agents** | Query databases, generate reports | ThoughtSpot, Snowflake Cortex |
| **Creative Agents** | Generate content, designs, music | Jasper, Runway, Suno |

---

## Where Our Project Fits

> [!map] AI Software Company Classification
> - **Architecture:** Hybrid (deliberative planning + reactive tool use)
> - **Capability:** Hierarchical (CEO → BA → Researcher → Architect → Engineer → PPT)
> - **Domain:** Multi-domain (coding + research + content)
> - **Pattern:** Orchestrator-Worker with Sequential Pipeline
> - **Autonomy:** Semi-autonomous with [[Approval Gate Design|human approval gates]]

See [[Agentic AI - Master Guide]] for the full picture.

#agentic-ai #agents #knowledge #classification
