# Agentic AI - Master Guide

> [!tldr] What is Agentic AI?
> An AI agent is a system that uses an LLM as its "brain" to **perceive** its environment, **make decisions**, **take actions**, and **learn** from results. Unlike a chatbot that responds to prompts, an agent operates **autonomously** — it can plan multi-step tasks, use tools, remember context, and adapt based on outcomes.

## The Shift: Chatbot → Agent

| | Chatbot | AI Agent |
|---|---|---|
| **Interaction** | Single prompt → single response | Goal → multi-step autonomous execution |
| **Memory** | Stateless (or short context) | Persistent memory across interactions |
| **Tools** | None | Can call APIs, databases, search, code |
| **Planning** | None | Decomposes goals into subtasks |
| **Autonomy** | Zero — waits for human input | Acts independently within guardrails |
| **Adaptation** | None | Learns from results, self-corrects |

## How We Got Here (Timeline)

```
2022 — ChatGPT launches (chatbot era)
2023 — AutoGPT, BabyAGI (autonomous agent experiments)
     — OpenAI Function Calling (tool use begins)
     — LangChain Agents (first framework)
2024 — CrewAI (role-based multi-agent)
     — LangGraph (stateful graph agents)
     — Anthropic MCP announced
     — OpenAI Swarm (experimental)
2025 — MCP adopted by all major providers
     — OpenAI Agents SDK (production-grade)
     — Google A2A protocol
     — Google Agent Development Kit (ADK)
     — Claude Agent SDK
2026 — Microsoft Agent Framework 1.0 (Semantic Kernel + AutoGen merged)
     — MCP crosses 97M monthly SDK downloads
     — Agentic AI becomes dominant enterprise pattern
     — LangGraph surpasses CrewAI in adoption
```

## Core Components of an AI Agent

Every agent has these building blocks:

```
┌─────────────────────────────────────┐
│            AI AGENT                 │
│                                     │
│  ┌───────────┐  ┌──────────────┐   │
│  │   LLM     │  │   Memory     │   │
│  │  (Brain)  │  │ (Short+Long) │   │
│  └─────┬─────┘  └──────┬───────┘   │
│        │               │           │
│  ┌─────┴───────────────┴─────┐     │
│  │       Reasoning Engine     │     │
│  │  (ReAct / Plan / Reflect) │     │
│  └─────────────┬─────────────┘     │
│                │                   │
│  ┌─────────────┴─────────────┐     │
│  │         Tool Use           │     │
│  │  APIs, Search, Code, DB   │     │
│  └───────────────────────────┘     │
│                                     │
│  ┌───────────────────────────┐     │
│  │    Guardrails & Gates     │     │
│  │  (Human-in-the-loop)      │     │
│  └───────────────────────────┘     │
└─────────────────────────────────────┘
```

1. **LLM (Brain)** — The language model that reasons, generates, and decides
2. **Memory** — Short-term (conversation context) + long-term (persistent knowledge)
3. **Reasoning Engine** — The loop pattern (ReAct, Plan-Execute, Reflection)
4. **Tool Use** — External capabilities (APIs, search, code execution, databases)
5. **Guardrails** — Safety boundaries, approval gates, human oversight

---

## Related Pages

- [[Types of AI Agents]] — Classification by architecture (reactive, deliberative, etc.)
- [[Agent Design Patterns]] — The 7 patterns every agent developer should know
- [[Multi-Agent Architectures]] — How agents work together (orchestrator, swarm, hierarchy)
- [[Agent Frameworks Comparison]] — LangGraph vs CrewAI vs AutoGen vs OpenAI SDK
- [[Agent Protocols - MCP and A2A]] — How agents connect to tools and each other
- [[Agentic AI Use Cases]] — Real-world production applications
- [[Our AI Software Company]] — How our project uses these concepts

#agentic-ai #agents #knowledge #hackathon
