# Multi-Agent Architectures

How multiple AI agents work together. Three dominant topologies in 2026.

---

## 1. Orchestrator-Worker (Most Common — ~70% of production)

> A central orchestrator agent decomposes goals, routes subtasks to specialist workers, and aggregates results.

```
         ┌────────────────┐
         │  ORCHESTRATOR   │
         │ (decomposes,    │
         │  routes, merges) │
         └──┬────┬────┬───┘
            │    │    │
            ▼    ▼    ▼
         ┌───┐┌───┐┌───┐
         │ W1││ W2││ W3│
         └───┘└───┘└───┘
         Workers don't talk
         to each other
```

**Characteristics:**
- Single point of control and traceability
- Workers are independent — don't communicate with each other
- All coordination flows through orchestrator
- Easy to debug (one control flow)
- Latency: 2-5 seconds per delegation cycle

**When to use:** Most multi-agent tasks. Default choice.

**Examples:** Customer support routing, content pipelines, our [[Pipeline Flow|AI Software Company]]

---

## 2. Supervisor-Hierarchical

> Tiered structure where higher-level agents supervise teams of lower-level agents.

```
              ┌──────────┐
              │   CEO     │
              └──┬────┬───┘
                 │    │
          ┌──────┘    └──────┐
          ▼                  ▼
     ┌─────────┐       ┌─────────┐
     │ Manager │       │ Manager │
     │   A     │       │   B     │
     └──┬──┬───┘       └──┬──┬───┘
        │  │              │  │
        ▼  ▼              ▼  ▼
      ┌──┐┌──┐          ┌──┐┌──┐
      │W1││W2│          │W3││W4│
      └──┘└──┘          └──┘└──┘
```

**Characteristics:**
- Multiple levels of supervision
- Higher levels: coordination and planning
- Lower levels: task execution
- Scales well for complex enterprise workflows
- Each manager can run its own orchestration loop

**When to use:** Large-scale systems with multiple teams of agents.

**Examples:** Enterprise automation (HR + Finance + IT teams), complex research with sub-teams

---

## 3. Swarm (Peer-to-Peer, No Central Control)

> Peer agents communicate directly. No single coordinator. Emergent behavior.

```
     ┌───┐     ┌───┐
     │ A │◄───►│ B │
     └─┬─┘     └─┬─┘
       │  ╲   ╱  │
       │   ╲ ╱   │
       │    ╳    │
       │   ╱ ╲   │
       ▼  ╱   ╲  ▼
     ┌───┐     ┌───┐
     │ C │◄───►│ D │
     └───┘     └───┘
     Everyone talks to everyone
```

**Characteristics:**
- No central coordinator — agents self-organize
- Agents can hand off tasks to each other directly
- Emergent behavior from local interactions
- Hardest to debug and predict
- Most flexible but most chaotic

**When to use:** Research experiments, creative brainstorming, problems where the solution path is unknown.

**Examples:** OpenAI Swarm (experimental), debate-style AI systems

---

## 4. Pipeline (Sequential Chain)

> Agents execute in a fixed order. Each agent's output feeds the next.

```
A → B → C → D → E → F
```

**Characteristics:**
- Predictable, deterministic flow
- Easy to monitor and debug
- Each agent has a clear input/output contract
- Approval gates can be inserted between any step
- Doesn't handle dynamic routing

**When to use:** When the task naturally decomposes into ordered steps.

**Examples:** Our AI Software Company (CEO→BA→Researcher→Architect→Engineer→PPT)

---

## 5. DAG (Directed Acyclic Graph)

> Agents execute based on dependency graph — parallelism where possible.

```
     ┌───┐
     │ A │
     └─┬─┘
    ╱     ╲
   ▼       ▼
┌───┐   ┌───┐
│ B │   │ C │  ← B and C run in parallel
└─┬─┘   └─┬─┘
   ╲     ╱
     ▼ ▼
    ┌───┐
    │ D │  ← D waits for both B and C
    └───┘
```

**Characteristics:**
- Parallel execution where dependencies allow
- Faster than pure sequential
- More complex to orchestrate
- Need dependency tracking

**When to use:** When some subtasks are independent and can run simultaneously.

---

## Comparison Table

| Architecture | Control | Debugging | Scalability | Flexibility | Our Project |
|-------------|---------|-----------|-------------|-------------|-------------|
| **Orchestrator-Worker** | Centralized | Easy | Good | Medium | Partially |
| **Hierarchical** | Layered | Medium | Excellent | Good | No |
| **Swarm** | None | Hard | Variable | Highest | No |
| **Pipeline** | Sequential | Easiest | Limited | Low | **Yes** |
| **DAG** | Dependency | Medium | Good | Medium | No (future?) |

---

## Communication Patterns

### Shared Memory (Blackboard)
All agents read/write to a shared state store.
```
Agent A writes → [Shared Memory] ← Agent B reads
```
**Our project uses this** — agents share memory via the database.

### Message Passing
Agents send messages to each other directly or via a broker.
```
Agent A —message→ Agent B
```
**Frameworks:** AutoGen, A2A protocol

### Event-Driven
Agents subscribe to events and react when relevant events fire.
```
Event: "BA_COMPLETED" → triggers Researcher to start
```
**Our project uses this** — WebSocket events trigger UI updates.

---

See [[Agentic AI - Master Guide]] | [[Agent Design Patterns]] | [[Agent Frameworks Comparison]]

#agentic-ai #multi-agent #architecture #knowledge
