# How to Build AI Agents — Every Approach (2026)

All the ways to build an AI agent, from drag-and-drop to raw code. Organized by complexity.

---

## The Spectrum

```
No-Code ◄──────────────────────────────────────────────► Full Code

 Zapier    n8n     Dify    CrewAI   LangGraph   Claude    Raw API
 Lindy   FlowiseAI         OpenAI SDK          Agent SDK   Calls
                                    Google ADK
```

---

## Level 1: No-Code Platforms (Drag & Drop)

Build agents without writing any code. Visual interfaces, pre-built templates.

### Zapier AI Agents
| Aspect | Details |
|--------|---------|
| **What** | AI automation on top of Zapier's 7,000+ app integrations |
| **How** | Natural language instructions + Zapier workflow triggers |
| **Best for** | Business users, connecting existing SaaS tools |
| **Limitation** | Limited reasoning, can't handle complex multi-step logic |
| **Pricing** | From $20/month (includes AI features in paid plans) |

```
Trigger (email arrives) → AI Agent (classify, decide) → Action (respond, tag, forward)
```

### Lindy
| Aspect | Details |
|--------|---------|
| **What** | No-code agent builder with visual workflow editor |
| **How** | Configure triggers, actions, conditions, and agent steps visually |
| **Best for** | Personal assistants, email management, scheduling |
| **Pricing** | From $50/month |

### Relevance AI
| Aspect | Details |
|--------|---------|
| **What** | Low-code platform for multi-agent teams |
| **How** | Build individual agents, give them tools, organize into teams |
| **Best for** | Sales, support, research agent teams |
| **Pricing** | From $19/month |

### MindStudio
| Aspect | Details |
|--------|---------|
| **What** | Visual AI app builder with agent capabilities |
| **How** | Drag-and-drop workflow builder + AI model selection |
| **Best for** | Custom AI apps, internal tools |

---

## Level 2: Low-Code Platforms (Visual + Some Code)

Visual builders with the option to add custom code when needed.

### n8n (What We Use)

| Aspect | Details |
|--------|---------|
| **What** | Open-source workflow automation with native AI agent nodes |
| **How** | Visual canvas + AI Agent nodes + 400+ integrations |
| **Self-hosted** | Yes (Docker, our instance: srv1867770.hstgr.cloud) |
| **Pricing** | Free (self-hosted), from $24/month (cloud) |

**n8n AI Agent Architecture:**

```
┌─────────────────────────────────────────────────────┐
│                  n8n AI Agent Node                    │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐ │
│  │  System   │  │   LLM    │  │  Tools            │ │
│  │  Prompt   │  │ (Claude/ │  │  ├── HTTP Request  │ │
│  │          │  │  GPT/     │  │  ├── Code Execute  │ │
│  │          │  │  Gemini)  │  │  ├── Vector Store  │ │
│  │          │  │          │  │  ├── Calculator     │ │
│  │          │  │          │  │  ├── MCP Client     │ │
│  │          │  │          │  │  └── Custom Tool    │ │
│  └──────────┘  └──────────┘  └───────────────────┘ │
│                                                     │
│  ┌──────────┐  ┌───────────────────────────────────┐│
│  │  Memory  │  │  Execution Mode: ReAct            ││
│  │  (Chat   │  │  (Reason → Act → Observe → Loop)  ││
│  │  History)│  │                                   ││
│  └──────────┘  └───────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

**Key n8n Features (2026):**
- **AI Agent Node** — Wraps LLM + memory + tools into an autonomous agent
- **MCP Client & Server** — Connect to any MCP-compatible tool ecosystem
- **Model routing** — Simple queries → GPT-4o-mini, complex → Claude Sonnet
- **ReAct mode** — Agent reasons, acts, observes, loops until done
- **Sub-workflows as tools** — Any n8n workflow can become an agent tool
- **400+ integrations** — Slack, Gmail, Google Sheets, Airtable, databases, APIs
- **Self-hosted** — Full control, no data leaves your server

**Three Ways n8n Uses MCP (2026):**
1. **MCP Client Tool** — Your n8n agent calls external MCP servers (e.g., filesystem, GitHub, database MCP servers)
2. **MCP Server Trigger** — Expose your n8n workflows as MCP tools that other agents can call
3. **AI Agent Tool node** — One agent supervises other agents on the same canvas

**Example: n8n AI Agent Workflow**
```
Webhook → AI Agent Node (Claude 3.5 Sonnet)
              ├── Tool: Google Search
              ├── Tool: Airtable (read/write leads)
              ├── Tool: Gmail (send email)
              └── Tool: Code Execute (analyze data)
           → Respond with results
```

### Dify
| Aspect | Details |
|--------|---------|
| **What** | Open-source LLM app development platform |
| **How** | Visual prompt orchestration + agent workflows + RAG |
| **Self-hosted** | Yes (Docker) |
| **Best for** | RAG applications, chatbots with retrieval, agent workflows |
| **Pricing** | Free (self-hosted), from $59/month (cloud) |

### FlowiseAI
| Aspect | Details |
|--------|---------|
| **What** | Open-source visual builder for LangChain/LlamaIndex flows |
| **How** | Drag-and-drop LangChain components onto a canvas |
| **Self-hosted** | Yes (npm install) |
| **Best for** | Prototyping LangChain agents without code |

### Google Cloud Vertex AI Agent Builder
| Aspect | Details |
|--------|---------|
| **What** | Enterprise agent builder on Google Cloud |
| **How** | Visual builder + Gemini models + Google integrations |
| **Best for** | Enterprise deployments on GCP |
| **Pricing** | Pay-per-use (Google Cloud pricing) |

---

## Level 3: Code Frameworks (Python/TypeScript)

Full control via code. The professional developer's path.

### Claude Agent SDK (What We Should Know Best)

| Aspect | Details |
|--------|---------|
| **What** | Anthropic's agent framework — same engine that powers Claude Code |
| **How** | Python/TypeScript SDK with agent loop, tools, subagents |
| **Models** | Claude family (Sonnet, Opus, Haiku) |
| **Key feature** | Hierarchical subagents with isolated context windows |
| **Pricing** | Pay per API token (Claude API pricing) |

**Architecture:**
```
┌─────────────────────────────────────────┐
│           Claude Agent SDK               │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │         Agent Loop              │    │
│  │  Model call → Tool use →        │    │
│  │  Observe result → Loop          │    │
│  └──────────┬──────────────────────┘    │
│             │                           │
│  ┌──────────▼──────────┐               │
│  │    Built-in Tools    │               │
│  │  • File read/write   │               │
│  │  • Shell commands    │               │
│  │  • Web search        │               │
│  │  • MCP tools         │               │
│  └──────────────────────┘               │
│                                         │
│  ┌──────────────────────┐               │
│  │    Custom Tools      │               │
│  │  (Your functions     │               │
│  │   registered as MCP) │               │
│  └──────────────────────┘               │
│                                         │
│  ┌──────────────────────┐               │
│  │    Subagents         │               │
│  │  • Own context window│               │
│  │  • Own tools         │               │
│  │  • Own model choice  │               │
│  │  • Report back to    │               │
│  │    parent agent      │               │
│  └──────────────────────┘               │
└─────────────────────────────────────────┘
```

**How MCP Works with Claude Agent SDK:**
```python
from claude_agent_sdk import Agent, tool

# Define a custom tool (automatically becomes MCP tool)
@tool
def search_database(query: str) -> str:
    """Search our product database"""
    results = db.search(query)
    return json.dumps(results)

# Create agent with tools
agent = Agent(
    model="claude-sonnet-4-20250514",
    tools=[search_database],
    system_prompt="You are a product research assistant..."
)

# Run the agent loop
result = agent.run("Find all products under $50 with 4+ star ratings")
```

**Subagent Pattern:**
```python
# Main agent delegates to specialized subagents
main_agent = Agent(
    model="claude-opus-4-20250514",
    subagents=[
        Agent(name="researcher", model="claude-sonnet-4-20250514", tools=[web_search]),
        Agent(name="coder", model="claude-sonnet-4-20250514", tools=[file_write, shell]),
        Agent(name="reviewer", model="claude-haiku-4-5-20251001", tools=[file_read]),
    ]
)
```

### OpenAI Agents SDK

```python
from agents import Agent, handoff, Runner

triage = Agent(
    name="Triage",
    instructions="Route customer to the right specialist",
    handoffs=[billing_agent, technical_agent, sales_agent]
)

billing_agent = Agent(
    name="Billing",
    instructions="Handle billing questions",
    tools=[lookup_invoice, process_refund]
)

result = Runner.run(triage, "I was charged twice for my subscription")
```

### LangGraph

```python
from langgraph.graph import StateGraph, MessagesState

graph = StateGraph(MessagesState)
graph.add_node("researcher", research_node)
graph.add_node("writer", writer_node)
graph.add_node("reviewer", reviewer_node)

graph.add_edge("researcher", "writer")
graph.add_conditional_edges("reviewer", should_revise, {
    "revise": "writer",
    "approve": END
})

app = graph.compile()
result = app.invoke({"messages": [("user", "Write a report on AI agents")]})
```

### CrewAI

```python
from crewai import Agent, Task, Crew

researcher = Agent(role="Researcher", goal="Find facts", llm="gpt-4o")
writer = Agent(role="Writer", goal="Write report", llm="gpt-4o")

research_task = Task(description="Research AI agents", agent=researcher)
write_task = Task(description="Write a report", agent=writer)

crew = Crew(agents=[researcher, writer], tasks=[research_task, write_task])
result = crew.kickoff()
```

### Google Agent Development Kit (ADK)

```python
from google.adk import Agent

agent = Agent(
    model="gemini-2.0-flash",
    tools=[google_search, code_execution],
    a2a_enabled=True  # Can be discovered by other agents
)
```

---

## Level 4: Raw API Calls (What We Built)

Direct LLM API calls with custom orchestration. Maximum control, maximum effort.

### Our Approach

```python
# Our AI Software Company — custom agent orchestration
async def run_agent(agent_name, context):
    response = await call_openrouter(
        model=get_model_for_agent(agent_name),
        system_prompt=AGENT_PROMPTS[agent_name],
        user_message=build_context(context),
        temperature=0.7
    )
    return parse_json_output(response)

# Custom pipeline orchestration
async def run_pipeline(problem_statement):
    ceo_output = await run_agent("ceo", problem_statement)
    # Gate 1: Wait for founder approval
    ba_output = await run_agent("business_analyst", ceo_output)
    # Gate 2: Wait for founder approval
    # ... and so on through all 6 agents
```

**Why we chose this:**
- Full control over pipeline flow
- No framework overhead or lock-in
- Custom approval gate system
- Direct OpenRouter API = use any model
- Simple enough for our sequential pipeline

---

## Comparison Matrix

| Approach | Complexity | Flexibility | Cost | Time to MVP | Best For |
|----------|-----------|------------|------|-------------|----------|
| **Zapier** | Very Low | Low | $$$ | Hours | Business automation |
| **n8n** | Low | Medium | $ (self-host) | Hours–Days | Workflow agents with integrations |
| **Dify** | Low | Medium | $ (self-host) | Days | RAG + chatbot agents |
| **FlowiseAI** | Low–Med | Medium | Free | Days | LangChain prototyping |
| **CrewAI** | Medium | Medium | Free | Days | Quick multi-agent prototypes |
| **OpenAI SDK** | Medium | Medium | Token cost | Days | GPT-centric agents |
| **Claude Agent SDK** | Medium | High | Token cost | Days | Claude-powered, subagent pattern |
| **LangGraph** | High | Very High | Free + tokens | Weeks | Production stateful workflows |
| **Google ADK** | Medium | High | Token cost | Days | Cross-framework via A2A |
| **Raw API** | Very High | Maximum | Token cost | Weeks | Custom everything (our approach) |

---

## Decision Tree

```
Want to build an agent?
│
├── Can you write code?
│   ├── NO → Use n8n (self-hosted, visual, powerful)
│   │         or Zapier (easiest, most integrations)
│   │         or Dify (if you need RAG)
│   │
│   └── YES →
│       ├── Quick prototype? → CrewAI (30 lines of code)
│       ├── Claude-powered? → Claude Agent SDK
│       ├── GPT-powered? → OpenAI Agents SDK
│       ├── Google ecosystem? → Google ADK
│       ├── Production stateful? → LangGraph
│       ├── Full control? → Raw API calls (our approach)
│       └── Voice/call agent? → Vapi / ElevenLabs / LiveKit
│
└── Enterprise?
    ├── Microsoft stack → Copilot Studio / Semantic Kernel
    ├── Google Cloud → Vertex AI Agent Builder
    ├── Salesforce → Agentforce
    └── AWS → Bedrock Agents / Strands
```

---

## Our Knowledge Map

| Approach | Our Experience Level |
|----------|---------------------|
| **n8n** | Active — running on srv1867770, webhook events for our pipeline |
| **Claude Agent SDK via MCP** | Familiar — we use Claude Code daily, understand the agent loop |
| **Raw API calls** | Expert — built our entire 6-agent pipeline this way |
| **Zapier** | Aware — know the concept |
| **LangGraph** | Aware — studied architecture, didn't use |
| **CrewAI** | Aware — studied, our design is similar (roles + tasks) |
| **Google Cloud** | Aware — know Vertex AI concepts |

---

## The n8n + Claude SDK Connection

Our stack uses BOTH:

```
n8n (webhook layer) ◄──── Event notifications ────► Our Pipeline (raw API)
                                                        │
                                                   Uses Claude/GPT
                                                   via OpenRouter
```

**n8n handles:** Webhook events, notifications, external integrations
**Our code handles:** Agent orchestration, approval gates, output generation

**Potential evolution:** We could rebuild our entire pipeline IN n8n using AI Agent nodes — each agent as an n8n AI Agent node chained together. But the custom code gives us more control for the hackathon demo.

---

See [[Agent Frameworks Comparison]] | [[AI Agent Market - Competitors]] | [[Agent Protocols - MCP and A2A]]

#agentic-ai #how-to-build #frameworks #n8n #claude-sdk #MCP #knowledge
