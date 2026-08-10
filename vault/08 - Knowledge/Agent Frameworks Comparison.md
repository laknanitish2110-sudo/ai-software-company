# Agent Frameworks Comparison

The major agentic AI frameworks as of mid-2026. The ecosystem has consolidated into 6-8 serious options.

---

## The Big 6

### 1. LangGraph (LangChain)
> Graph-based stateful agent workflows

- **Architecture:** Nodes (agent steps) + Edges (transitions) = Graph
- **Best for:** Complex production workflows needing state, persistence, human-in-the-loop
- **Language:** Python, JavaScript
- **State management:** Built-in persistence, checkpointing, replay
- **Key strength:** Auditability — every step is traceable, rollback-able
- **Weakness:** Steep learning curve
- **Adoption:** Surpassed CrewAI in GitHub stars in early 2026
- **Status:** Production-ready. Enterprise favorite.

```python
from langgraph.graph import StateGraph
graph = StateGraph(AgentState)
graph.add_node("research", research_agent)
graph.add_node("write", writer_agent)
graph.add_edge("research", "write")
```

---

### 2. CrewAI
> Role-based multi-agent teams

- **Architecture:** Agents with roles + Tasks + Crew (team)
- **Best for:** Quick multi-agent prototypes with role-based collaboration
- **Language:** Python
- **Key strength:** Fastest idea-to-prototype (30-60 lines of code)
- **Weakness:** Limited to sequential orchestration, teams outgrow it
- **Status:** Production-ready for medium complexity.

```python
from crewai import Agent, Task, Crew
researcher = Agent(role="Researcher", goal="Find data", llm=model)
writer = Agent(role="Writer", goal="Write report", llm=model)
crew = Crew(agents=[researcher, writer], tasks=[...])
crew.kickoff()
```

---

### 3. OpenAI Agents SDK
> Lightweight agent orchestration with handoffs

- **Architecture:** Agents with instructions + Functions + Handoffs
- **Best for:** GPT-centric agents with sandboxed tools and sub-agents
- **Language:** Python
- **Key strength:** First-class handoff primitive (agent A → agent B with context)
- **Weakness:** Tightly coupled to OpenAI models
- **Evolution:** Grew from experimental "Swarm" project
- **Status:** Production-ready.

```python
from agents import Agent, handoff
triage = Agent(name="Triage", instructions="Route to specialist")
billing = Agent(name="Billing", instructions="Handle billing questions")
triage.handoffs = [handoff(billing)]
```

---

### 4. Claude Agent SDK (Anthropic)
> Anthropic's agent framework with hierarchical sub-agents

- **Architecture:** Agent loop with tool use, sub-agent spawning
- **Best for:** Claude-powered agents, complex reasoning tasks
- **Language:** Python, TypeScript
- **Key strength:** Hierarchical subagent spawning (2026), strong safety guardrails
- **Weakness:** Claude-specific
- **Status:** Production-ready. Powers Claude Code.

---

### 5. AG2 (AutoGen successor)
> Community fork of Microsoft AutoGen — event-driven multi-agent conversations

- **Architecture:** Agents as conversation participants
- **Best for:** Multi-agent conversations, debate-style reasoning
- **Language:** Python
- **Key strength:** Flexible conversation patterns, async message passing
- **Weakness:** High token consumption, complex debugging
- **Status:** Active development. Community-driven.

---

### 6. Google Agent Development Kit (ADK)
> Google's multi-agent framework with A2A built-in

- **Architecture:** Multi-agent as default, A2A for cross-framework communication
- **Best for:** Google Cloud deployments, cross-framework agent networks
- **Language:** Python
- **Key strength:** A2A protocol for inter-agent discovery and communication
- **Status:** Production-ready (April 2025 launch).

---

## Also Notable

| Framework | Creator | Focus |
|-----------|---------|-------|
| **Microsoft Semantic Kernel** | Microsoft | Enterprise .NET, plugin-based, powers M365 Copilot |
| **LlamaIndex Workflows** | LlamaIndex | Data retrieval + RAG agents |
| **Pydantic AI V2** | Pydantic team | Type-safe agent definitions |
| **Strands Agents** | AWS | AWS-native agent framework |
| **Haystack** | deepset | Document processing agents |
| **Smolagents** | Hugging Face | Lightweight, code-first agents |

---

## Decision Matrix

| Need | Best Choice |
|------|-------------|
| Production stateful workflows | **LangGraph** |
| Quick multi-agent prototype | **CrewAI** |
| GPT-centric with handoffs | **OpenAI Agents SDK** |
| Claude-powered reasoning | **Claude Agent SDK** |
| Cross-framework agent network | **Google ADK + A2A** |
| .NET enterprise | **Semantic Kernel** |
| Multi-agent conversations | **AG2** |
| Data/RAG focused | **LlamaIndex** |

---

## What We Built (Custom)

> [!note] Our Approach
> We built a **custom orchestrator** rather than using a framework. Why?
> - Full control over the pipeline flow
> - No framework lock-in
> - Simple enough for our 6-agent sequential pipeline
> - Direct OpenRouter API calls (no framework overhead)
> - Custom approval gate system
>
> Our stack: FastAPI + python-pptx + OpenRouter + WebSockets
> See [[Orchestrator]] and [[Pipeline Flow]]

---

See [[Agentic AI - Master Guide]] | [[Agent Protocols - MCP and A2A]]

#agentic-ai #frameworks #comparison #knowledge
