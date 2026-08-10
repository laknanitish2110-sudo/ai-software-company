# Tech Stack

## Backend

| Component | Choice | Why |
|-----------|--------|-----|
| **Language** | Python 3.14 | Best AI/ML ecosystem, async support |
| **Framework** | FastAPI | Async, fast, auto-docs, WebSocket support |
| **Database** | SQLite (aiosqlite) | Zero config, portable, enough for v1 |
| **LLM Access** | OpenRouter (OpenAI SDK) | Access any model, single API key |
| **AI Gateway** | OmniRoute (localhost:20128) | Local model routing, caching, fallbacks (see [[OmniRoute Setup]]) |
| **Web Search** | Tavily Search | AI-optimized search, better results than DuckDuckGo (see [[Search API Comparison]]) |
| **PPTX** | python-pptx | Generate real PowerPoint files |
| **DOCX** | python-docx | Generate Word documents with formatting |
| **Webhooks** | httpx (async) | Send events to n8n (see [[n8n Integration]]) |

## Frontend

| Component | Choice | Why |
|-----------|--------|-----|
| **Framework** | Next.js 16 (App Router) | React + SSR, great DX |
| **Language** | TypeScript | Type safety |
| **Styling** | CSS Variables (Light Theme) | Custom design system, no framework dependency |
| **Icons** | Lucide React | Clean, consistent |
| **Real-time** | WebSocket (native) | Live activity updates |

> [!decision] Light Theme Design
> The frontend uses a custom **light theme** built with CSS variables — not Tailwind CSS. This gives full control over the design system and makes theming trivial (swap variable values for dark mode in V2). The accent color is `#635bff` (electric purple), matching this Obsidian vault.

## Infrastructure

| Component | Choice | Why |
|-----------|--------|-----|
| **Backend hosting** | Local (uvicorn) | v1 is personal tool |
| **Frontend hosting** | Local (next dev) | Same |
| **File storage** | Local filesystem | Generated projects saved to `generated_projects/` |
| **n8n Instance** | srv1867770.hstgr.cloud | Webhook event hub for external integrations |

## Key Files

```
backend/
├── app/core/config.py          # API keys, model config
├── app/core/database.py        # SQLite schema + queries
├── app/models/schemas.py       # Pydantic models, enums
├── app/agents/prompts.py       # System prompts for all 6 agents
├── app/agents/engine.py        # Agent execution + Call Employee
├── app/services/orchestrator.py # Pipeline + approval gates + cross-review
├── app/services/file_generator.py # Code → zip file
├── app/services/pptx_generator.py # Slides → .pptx file
├── app/services/docx_generator.py # Documentation → .docx file
├── app/services/webhook.py     # httpx → n8n webhook events
├── app/services/web_search.py  # Tavily AI-optimized web search
├── app/api/routes.py           # REST + WebSocket endpoints
└── app/main.py                 # FastAPI app entry point

frontend/
├── src/app/page.tsx            # Main page (Start → Dashboard)
├── src/components/StartProject.tsx  # Problem input form
├── src/components/Dashboard.tsx     # Main dashboard
├── src/components/Pipeline.tsx      # Visual pipeline progress
├── src/components/AgentOutput.tsx   # Output cards + approve/reject
├── src/components/CallEmployee.tsx  # Direct chat with agents
├── src/lib/api.ts              # API client functions
└── src/lib/constants.ts        # Agent config, labels
```

---

Related: [[Database Schema]], [[Search API Comparison]], [[OmniRoute Setup]], [[Model Strategy]], [[n8n Integration]]

#architecture #tech-stack
