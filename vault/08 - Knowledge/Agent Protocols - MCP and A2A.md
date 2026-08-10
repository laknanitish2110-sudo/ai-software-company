# Agent Protocols - MCP and A2A

The two protocols that standardize how agents connect to the world and to each other.

---

## MCP (Model Context Protocol)

> "USB-C for AI" — standardizes how an agent connects to tools, data, and services.

**Created by:** Anthropic (2024), donated to Linux Foundation's Agentic AI Foundation (Dec 2025)
**Adoption:** 97 million monthly SDK downloads by Feb 2026. Used by Anthropic, OpenAI, Google, Microsoft, Amazon.

### What it does
MCP standardizes the connection between an **AI agent** and its **tools**. Instead of every app building custom integrations, MCP provides one protocol.

```
┌──────────────┐     MCP      ┌──────────────┐
│   AI Agent   │◄────────────►│  MCP Server   │
│ (Claude,     │   JSON-RPC   │ (Tool/Data    │
│  GPT, etc)   │              │  Provider)    │
└──────────────┘              └──────────────┘
```

### Architecture
- **MCP Host** — The AI application (Claude Desktop, IDE, your app)
- **MCP Client** — Lives inside the host, maintains connection to servers
- **MCP Server** — Exposes tools, resources, and prompts via JSON-RPC

### What MCP Servers Provide
1. **Tools** — Functions the agent can call (search, file operations, API calls)
2. **Resources** — Data the agent can read (files, database records)
3. **Prompts** — Pre-built prompt templates for common tasks

### Example
```json
{
  "method": "tools/call",
  "params": {
    "name": "web_search",
    "arguments": { "query": "crop disease detection apps India" }
  }
}
```

### Why it matters
Before MCP: Every AI app needed N custom integrations for N tools.
With MCP: Build one MCP server, every AI app can use it.

**Our project:** We use MCP-compatible tool patterns (Tavily search, file generation) though not the MCP protocol directly.

---

## A2A (Agent-to-Agent Protocol)

> Standardizes how agents discover and communicate with each other across different frameworks.

**Created by:** Google (2025)

### What it does
While MCP connects agents to tools (vertical), A2A connects agents to other agents (horizontal).

```
┌──────────────┐     A2A      ┌──────────────┐
│   Agent A    │◄────────────►│   Agent B     │
│ (LangGraph)  │   HTTP/SSE   │ (CrewAI)      │
└──────────────┘              └──────────────┘
```

### Key Concepts

**Agent Cards** — Machine-readable description of an agent's capabilities
```json
{
  "name": "ResearchAgent",
  "description": "Finds and synthesizes research papers",
  "capabilities": ["web_search", "summarization"],
  "input_modalities": ["text"],
  "output_modalities": ["text", "json"],
  "auth": { "type": "api_key" }
}
```

**Task Lifecycle:**
1. Agent A discovers Agent B via its Agent Card
2. Agent A sends a task request
3. Agent B processes (may stream updates)
4. Agent B returns result
5. Agent A incorporates result

### Why it matters
Without A2A: Agents from different frameworks can't talk to each other.
With A2A: A LangGraph agent can delegate to a CrewAI agent seamlessly.

---

## How They Work Together

```
MCP = Vertical (agent ↔ tools)
A2A = Horizontal (agent ↔ agent)

         ┌─────────────────────────────┐
         │        Agent Network         │
         │                             │
         │  Agent A ◄──A2A──► Agent B  │
         │    │                  │      │
         │   MCP                MCP    │
         │    │                  │      │
         │    ▼                  ▼      │
         │  Tools             Tools    │
         │  (Search,          (DB,     │
         │   Files)            API)    │
         └─────────────────────────────┘
```

| | MCP | A2A |
|---|---|---|
| **Purpose** | Agent ↔ Tools | Agent ↔ Agent |
| **Direction** | Vertical | Horizontal |
| **Created by** | Anthropic | Google |
| **Protocol** | JSON-RPC | HTTP + SSE |
| **Discovery** | Server configuration | Agent Cards |
| **Adopted by** | All major providers | Growing adoption |

---

## Also Relevant: Function Calling

Before MCP, each LLM provider had their own tool-use mechanism:

| Provider | Mechanism |
|----------|-----------|
| **OpenAI** | Function Calling (2023) |
| **Anthropic** | Tool Use in Claude API |
| **Google** | Function Declarations in Gemini |

MCP is the **universal successor** — one protocol to replace provider-specific function calling patterns.

---

## Future Direction

By late 2026:
- MCP + A2A expected to become the standard agent infrastructure layer
- Every major cloud provider building MCP server ecosystems
- Enterprise "agent marketplaces" where agents discover and hire each other via A2A
- Governance and security layers being added (ACP — Agent Communication Protocol proposals)

---

See [[Agentic AI - Master Guide]] | [[Agent Frameworks Comparison]]

#agentic-ai #protocols #MCP #A2A #knowledge
