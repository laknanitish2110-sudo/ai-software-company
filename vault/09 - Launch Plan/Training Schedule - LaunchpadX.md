# Training & Build Schedule — SIH to LaunchpadX

> **Goal:** Train teammates on agentic AI + actually build agents together
> **Today:** Aug 10, 2026 (Sunday)
> **SIH:** Aug 18-19 (Monday-Tuesday)
> **LaunchpadX:** Aug 22-23 (Friday-Saturday) @ SNIST Hyderabad
> **Theme:** Agentic AI / GenAI / Agent Building

---

## Overview (13 Days)

```
Aug 10-12  │ PHASE 1: LEARN (Theory + Concepts)
Aug 13-15  │ PHASE 2: BUILD (Hands-on Agent Building)
Aug 16-17  │ PHASE 3: PREP SIH (Polish + Demo Practice)
Aug 18-19  │ ████ SIH HACKATHON ████
Aug 20-21  │ PHASE 4: LEVEL UP (Advanced + LaunchpadX Prep)
Aug 22-23  │ ████ LAUNCHPADX HACKATHON ████
```

---

## PHASE 1: LEARN — Theory & Concepts
### Day 1 — Sun Aug 10: "What is Agentic AI?"

**Morning (2-3 hrs) — Theory Session**

| Topic | Resource | Duration |
|-------|----------|----------|
| What is an AI agent vs chatbot | [[Agentic AI - Master Guide]] | 30 min |
| 6 types of agents (Russell & Norvig) | [[Types of AI Agents]] | 30 min |
| 7 design patterns (ReAct, Reflection, Planning...) | [[Agent Design Patterns]] | 45 min |
| Multi-agent architectures (Pipeline, Swarm, DAG) | [[Multi-Agent Architectures]] | 30 min |
| Q&A / Discussion | — | 15 min |

**Afternoon (2 hrs) — Show & Tell**

| Activity | Details |
|----------|---------|
| Demo our AI Software Company | Run the full pipeline live — problem → deliverables |
| Walk through the code | Show how 6 agents are orchestrated in `engine.py` |
| Map concepts to our project | Use [[Our AI Software Company]] as the guide |
| Assign reading | Each teammate reads 2 knowledge pages before tomorrow |

**Homework:**
- [ ] Everyone reads [[Agent Frameworks Comparison]] and [[Agent Protocols - MCP and A2A]]
- [ ] Each person picks a framework they want to try (n8n, Claude SDK, CrewAI, or LangGraph)

---

### Day 2 — Mon Aug 11: "How Agents Connect to the World"

**Morning (2-3 hrs) — Protocols & Tools**

| Topic | Resource | Duration |
|-------|----------|----------|
| MCP — "USB-C for AI" | [[Agent Protocols - MCP and A2A]] | 30 min |
| A2A — agent-to-agent communication | [[Agent Protocols - MCP and A2A]] | 20 min |
| RAG — how agents access knowledge | [[RAG - Retrieval Augmented Generation]] | 45 min |
| Voice & Call agents | [[Voice Agents]] + [[Call Agents]] | 30 min |
| The market — who's building what | [[AI Agent Market - Competitors]] | 20 min |

**Afternoon (2-3 hrs) — Hands-on: First Agent**

| Activity | Details |
|----------|---------|
| Install tools | Python 3.11+, Node.js, n8n (Docker), Claude CLI |
| Build "Hello Agent" | Simple ReAct agent using OpenAI/Claude API — ask question, use web search tool, answer |
| Everyone builds one | Each person writes a 30-line agent that uses at least 1 tool |

**Code template for first agent:**
```python
# hello_agent.py — Everyone's first agent
import openai

client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key="...")

tools = [{
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web for information",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
    }
}]

response = client.chat.completions.create(
    model="openai/gpt-4o-mini",
    messages=[{"role": "user", "content": "What's the weather in Hyderabad today?"}],
    tools=tools
)
# Handle tool calls, execute, feed back — the agent loop!
```

**Homework:**
- [ ] Modify your agent to use 2 tools (search + calculator)
- [ ] Read [[How to Build AI Agents]] — pick which Level you want to go deeper on

---

### Day 3 — Tue Aug 12: "Frameworks Deep Dive"

**Morning (2-3 hrs) — Framework Workshop**

Split into groups based on interest:

| Group | Framework | What They Build | Guide |
|-------|-----------|----------------|-------|
| **Group A** | n8n | AI agent workflow on our n8n instance | [[How to Build AI Agents]] Level 2 |
| **Group B** | Claude Agent SDK | Agent with subagents and MCP tools | [[How to Build AI Agents]] Level 3 |
| **Group C** | CrewAI / LangGraph | Multi-agent crew with roles | [[How to Build AI Agents]] Level 3 |

**Afternoon (2-3 hrs) — Build Sprint #1**

| Activity | Details |
|----------|---------|
| Each group builds a working agent | Must take input → reason → use tools → produce output |
| Cross-demo | Each group demos to the others (10 min each) |
| Discuss trade-offs | Which framework was easiest? Most powerful? Most flexible? |

**Deliverable:** Each group has a working agent they can demo.

---

## PHASE 2: BUILD — Hands-on Agent Building
### Day 4 — Wed Aug 13: "Build a Multi-Agent System"

**Full Day (5-6 hrs) — Team Build**

| Time | Activity |
|------|----------|
| 9:00-10:00 | Design session — sketch a 3-agent pipeline on whiteboard |
| 10:00-13:00 | Build it — each person owns one agent |
| 14:00-16:00 | Integration — connect agents, test the pipeline |
| 16:00-17:00 | Debug and polish |

**Project idea:** Build a mini version of our AI Software Company with 3 agents:
1. **Planner Agent** — takes a problem, creates a plan
2. **Researcher Agent** — searches the web, gathers info
3. **Writer Agent** — produces a report using plan + research

This teaches: agent handoffs, shared state, tool use, output parsing.

---

### Day 5 — Thu Aug 14: "Add RAG + Advanced Features"

**Morning (3 hrs) — RAG Workshop**

| Activity | Details |
|----------|---------|
| Set up a vector database | ChromaDB (local, easy) or Pinecone (cloud) |
| Embed documents | Chunk → embed → store the SIH problem statements |
| Build a RAG agent | Query the vector store, get grounded answers |

**Afternoon (3 hrs) — Advanced Patterns**

| Activity | Details |
|----------|---------|
| Add cross-review | Agent A reviews Agent B's output (our pattern) |
| Add approval gates | Human-in-the-loop: pause, show output, wait for approval |
| Add memory | Agent remembers context from previous interactions |
| Test with real problems | Use SIH problem statements as input |

---

### Day 6 — Fri Aug 15: "n8n Agent Workflows + Integration"

**Morning (3 hrs) — n8n Deep Dive**

| Activity | Details |
|----------|---------|
| Connect to our n8n instance | srv1867770.hstgr.cloud |
| Build an AI Agent workflow | Webhook trigger → AI Agent → response |
| Add MCP tools | Connect MCP servers to n8n |
| Chain agents | Agent 1 output → Agent 2 input in n8n |

**Afternoon (3 hrs) — Build Something Demoable**

| Activity | Details |
|----------|---------|
| Each person builds one complete agent workflow in n8n | Must be demoable |
| Combine into a team showcase | "Here are 4 different agents we built in n8n" |
| Record a 2-min walkthrough | Screen record for reference |

---

## PHASE 3: PREP SIH
### Day 7 — Sat Aug 16: "SIH Strategy & Polish"

**Morning (3 hrs) — SIH Problem Analysis**

| Activity | Details |
|----------|---------|
| Review SIH problem statements | Pick top 3 candidates |
| Map each to our pipeline | Which ones work best with our system? |
| Design the solution approach | For each candidate, sketch the 6-agent pipeline |
| Prepare backup plans | What if the API is down? Demo mode ready? |

**Afternoon (3 hrs) — System Testing**

| Activity | Details |
|----------|---------|
| Full pipeline test run | Problem → all 6 agents → deliverables |
| Test demo/fallback mode | Cached responses work? |
| Fix any bugs | Last chance for code fixes |
| Prepare the dev environment | All API keys working, servers running |

---

### Day 8 — Sun Aug 17: "Demo Practice & Final Prep"

**Morning (2 hrs) — Presentation Prep**

| Activity | Details |
|----------|---------|
| Write the pitch script | 5-min pitch for judges |
| Assign speaking roles | Who presents what |
| Create the demo flow | Step-by-step what to show |

**Afternoon (3 hrs) — Rehearsal**

| Activity | Details |
|----------|---------|
| Full dry run #1 | Time it, note issues |
| Fix issues | Adjust timing, fix demo glitches |
| Full dry run #2 | Should be smooth |
| Backup plan rehearsal | Practice demo mode in case of failures |
| Pack for hackathon | Laptops charged, hotspot ready, extension cords |

---

## ████ SIH HACKATHON — Aug 18-19 (Mon-Tue) ████

> Focus: Execute. Build. Demo. Win.
> Take notes on what judges ask — those insights help for LaunchpadX.

---

## PHASE 4: LEVEL UP — LaunchpadX Prep
### Day 9 — Wed Aug 20: "Post-SIH Debrief + LaunchpadX Strategy"

**Morning (2 hrs) — Debrief**

| Activity | Details |
|----------|---------|
| What worked at SIH? | List wins |
| What didn't work? | List problems and fixes |
| Judge feedback | What did they ask? What impressed them? |
| Code fixes | Fix anything that broke during SIH |

**Afternoon (3 hrs) — LaunchpadX Pivoting**

| Activity | Details |
|----------|---------|
| Review LaunchpadX theme | "Agentic AI / GenAI / Agent Building" |
| Decide: enhance existing or build new? | Our AI Software Company IS an agent-building project |
| Plan new features for LaunchpadX | What can we add in 2 days? |
| Assign tasks | Each person owns a feature |

**LaunchpadX-specific features to consider:**
- [ ] Live agent builder UI (drag-and-drop agent creation)
- [ ] Voice interface (Vapi integration for voice input)
- [ ] MCP server that exposes our pipeline as a tool
- [ ] Agent marketplace concept (browse pre-built agent templates)
- [ ] Real-time agent visualization (watch agents think)

---

### Day 10 — Thu Aug 21: "Build for LaunchpadX"

**Full Day (6-8 hrs) — Build Sprint**

| Time | Activity |
|------|----------|
| 9:00-10:00 | Finalize feature list for LaunchpadX |
| 10:00-13:00 | Build sprint — everyone codes |
| 14:00-17:00 | Integration + testing |
| 17:00-18:00 | Demo rehearsal (LaunchpadX version) |
| 18:00-19:00 | Pack, prep, final checks |

**Pitch angle for LaunchpadX:**
> "We built an AI Software Company — a team of 6 AI agents that work as a startup. But more than that, we've mastered every approach to building agents: no-code with n8n, SDK with Claude Agent SDK, and custom orchestration. We didn't just build one agent — we built an agent factory."

---

## ████ LAUNCHPADX HACKATHON — Aug 22-23 (Fri-Sat) @ SNIST ████

> Theme: Agentic AI / GenAI / Agent Building
> Pitch: We ARE agent builders. Our project IS the proof.

---

## Daily Checklist Template

Use this for each training day:

```
□ Morning standup (5 min) — what are we learning/building today?
□ Theory/reading done
□ Hands-on exercise completed
□ Each person can explain what they built
□ Code committed / workflow saved
□ Evening review — what clicked, what's confusing?
```

---

## Tools Everyone Needs Installed

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3.11+** | Agent code | python.org |
| **Node.js 18+** | Frontend, n8n | nodejs.org |
| **Docker** | n8n self-hosted | docker.com |
| **Git** | Version control | git-scm.com |
| **VS Code** | Code editor | code.visualstudio.com |
| **Claude Code** | AI pair programmer | `npm install -g @anthropic-ai/claude-code` |
| **Obsidian** | Read the vault | obsidian.md |
| **Postman** | Test APIs | postman.com |

---

## Skill Progression Map

```
Day 1-2: Can EXPLAIN what agents are and how they work
Day 3:   Can COMPARE frameworks and choose the right one
Day 4-5: Can BUILD a multi-agent system with RAG
Day 6:   Can BUILD agent workflows in n8n
Day 7-8: Can DEMO and PITCH the project confidently
Day 9-10: Can ENHANCE and EXTEND the system for LaunchpadX
```

---

## Key Knowledge Pages (Reading List)

### Must-Read (Everyone)
1. [[Agentic AI - Master Guide]]
2. [[Types of AI Agents]]
3. [[Agent Design Patterns]]
4. [[Our AI Software Company]]
5. [[How to Build AI Agents]]

### Should-Read (At least 3)
6. [[Multi-Agent Architectures]]
7. [[Agent Frameworks Comparison]]
8. [[Agent Protocols - MCP and A2A]]
9. [[RAG - Retrieval Augmented Generation]]
10. [[AI Agent Market - Competitors]]

### Nice-to-Know
11. [[Voice Agents]]
12. [[Call Agents]]
13. [[Agentic AI Use Cases]]

---

See [[Project Vision]] | [[Roadmap]] | [[Our AI Software Company]]

#schedule #training #hackathon #launchpadx #SIH
