# AI Software Company

A multi-agent AI pipeline that simulates a full software company — from problem analysis to working code, architecture diagrams, and investor-ready presentations. Built for the **LaunchpadX Hackathon 2026**.

**Live Demo:** [http://200.141.8.126:3000](http://200.141.8.126:3000)

## How It Works

Enter a problem statement and watch 6 AI agents collaborate in real-time:

```
Problem Statement
       |
   [CEO Agent] ---- Analyzes problem, classifies deliverable type
       |
   [Business Analyst] ---- Requirements, user stories, acceptance criteria
       |
   [Researcher] ---- Market analysis, tech stack research, web search
       |
   [Architect] ---- System design, API specs, database schema
       |
   [Engineer] ---- Full working code / n8n workflow generation
       |
   [PPT Agent] ---- Investor-ready presentation slides
```

Each agent's output is cross-reviewed by a peer agent before moving to the next stage. The pipeline supports both **auto-pilot** (fully autonomous) and **manual approval** modes.

## Deliverables

After a pipeline run completes, you get:

- **Source Code** (.zip) — Full project with all files
- **Architecture Diagram** — Visual system design
- **Presentation** (.pptx) — Investor/pitch deck
- **Project Report** (.docx) — Comprehensive documentation
- **n8n Workflow** (.json) — Importable automation workflow (for workflow/hybrid projects)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLite (aiosqlite) |
| Frontend | Next.js, TypeScript, Tailwind CSS |
| LLM Providers | OpenRouter (6 keys), OpenAI, Gemini |
| Real-time | WebSocket with auto-reconnect |
| Workflow RAG | 19,800+ n8n workflow templates indexed |

## Architecture

- **Multi-provider routing** — Each agent gets a dedicated API key, with automatic cross-key failover on quota exhaustion (402), rate limits (429), or auth errors (401/403)
- **Streaming output** — Live token-by-token output visible in the dashboard
- **Cross-review** — Every agent output is peer-reviewed by another agent before approval
- **Workflow RAG** — Searches 19,800+ n8n workflow templates to find reusable components
- **Crash-resilient** — Debounced state refreshes, capped event streams, connection auto-recovery

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- At least 1 OpenRouter API key

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with your API keys
cat > .env << 'EOF'
OPENROUTER_API_KEY=sk-or-v1-your-key
OPENAI_API_KEY=your-openai-key
GEMINI_API_KEY=your-gemini-key
EOF

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Point to your backend
cat > .env.local << 'EOF'
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api
EOF

npm run build
npm start
```

Open **http://localhost:3000** in your browser.

## Multi-Key Setup (Recommended)

For best performance, configure 6 OpenRouter API keys — one per agent with zero sharing:

| Key | Agent | Fallback Key |
|-----|-------|-------------|
| Key 1 | CEO | Key 6 |
| Key 2 | Business Analyst | Key 5 |
| Key 3 | Researcher | Key 4 |
| Key 4 | Architect | Key 3 |
| Key 5 | Engineer (fallback) | Key 6 |
| Key 6 | PPT | Key 1 |

```env
OPENROUTER_API_KEY=sk-or-v1-key1
OPENROUTER_API_KEY_2=sk-or-v1-key2
OPENROUTER_API_KEY_3=sk-or-v1-key3
OPENROUTER_API_KEY_4=sk-or-v1-key4
OPENROUTER_API_KEY_5=sk-or-v1-key5
OPENROUTER_API_KEY_6=sk-or-v1-key6
```

## Default Models

| Agent | Primary Model | Fallback |
|-------|--------------|----------|
| CEO | Gemini 2.5 Flash | Gemini 2.5 Flash |
| Business Analyst | Claude Sonnet 4 | Gemini 2.5 Flash |
| Researcher | Gemini 2.5 Flash | Gemini 2.5 Flash |
| Architect | Claude Sonnet 4 | Gemini 2.5 Flash |
| Engineer | GPT-4o (OpenAI) / Claude Sonnet 4 | Claude Sonnet 4 |
| PPT | Gemini 2.5 Flash | Gemini 2.5 Flash |

All models are configurable via environment variables (`MODEL_CEO`, `MODEL_BA`, etc.).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects` | Create new project |
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/{id}` | Get project state |
| POST | `/api/projects/{id}/approve/{output_id}` | Approve/reject agent output |
| POST | `/api/projects/{id}/call` | Chat with an agent |
| GET | `/api/projects/{id}/download/code` | Download generated code |
| GET | `/api/projects/{id}/download/pptx` | Download presentation |
| GET | `/api/projects/{id}/download/docx` | Download report |
| WS | `/api/ws/{id}` | Real-time updates |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | Yes | — | Primary OpenRouter key |
| `OPENROUTER_API_KEY_2` to `_6` | No | — | Additional keys for per-agent routing |
| `OPENAI_API_KEY` | No | — | Direct OpenAI access for Engineer |
| `GEMINI_API_KEY` | No | — | Direct Gemini access |
| `SMART_MODEL` | No | `anthropic/claude-sonnet-4` | Default smart model |
| `FALLBACK_MODEL` | No | `google/gemini-2.5-flash` | Default fallback model |
| `DATABASE_PATH` | No | `company.db` | SQLite database path |
| `N8N_WEBHOOK_URL` | No | — | n8n webhook for sharing |

## License


