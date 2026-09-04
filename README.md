# AI Software Company

A multi-agent AI pipeline that simulates a full software company — from problem analysis to working code, architecture diagrams, and investor-ready presentations.

**Live Demo:** [https://ai-software-company-gold.vercel.app](https://ai-software-company-gold.vercel.app)

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

## Features

- **Smart Task Routing** — Classifies inputs into 5 pipeline routes (full product, workflow, research, presentation, hybrid) with route-specific prompts and guardrails
- **Domain Memory** — Learns from completed projects and applies domain knowledge to future ones
- **OAuth Login** — Sign in with GitHub, Google, or email/password
- **Live Code Preview** — Real-time preview of generated code via E2B sandboxes
- **Streaming Agent Chat** — Talk to any agent mid-pipeline with streaming responses
- **GitHub Push** — Push generated code directly to a GitHub repository
- **Shareable Links** — Share project results via unique URLs
- **Build & Test Execution** — Sandboxed code execution with build status tracking

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
| Backend | Python 3.11, FastAPI, SQLite / PostgreSQL |
| Frontend | Next.js 16, TypeScript, Tailwind CSS |
| Auth | JWT (HS256), GitHub OAuth, Google OAuth |
| LLM Providers | OpenRouter, OpenAI, Gemini |
| Real-time | WebSocket with auto-reconnect |
| Cache | Redis |
| Workflow RAG | 19,800+ n8n workflow templates indexed |
| Hosting | Vercel (frontend), Railway (backend) |

## Architecture

- **Multi-provider routing** — Each agent gets a dedicated API key, with automatic cross-key failover on quota exhaustion (402), rate limits (429), or auth errors (401/403)
- **Task routing** — Classifies inputs into 5 pipeline routes with route-specific prompts
- **Streaming output** — Live token-by-token output visible in the dashboard
- **Cross-review** — Every agent output is peer-reviewed by another agent before approval
- **Workflow RAG** — Searches 19,800+ n8n workflow templates to find reusable components
- **Domain memory** — Persists learnings across projects for better context
- **Crash-resilient** — Debounced state refreshes, capped event streams, connection auto-recovery

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- At least 1 OpenRouter API key

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env with your API keys (see .env.example)
cp .env.example .env
# Edit .env with your keys

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
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

npm run dev
```

Open **http://localhost:3000** in your browser.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes | Primary OpenRouter key |
| `OPENROUTER_API_KEY_2` to `_6` | No | Additional keys for per-agent routing |
| `OPENAI_API_KEY` | No | Direct OpenAI access for Engineer |
| `GEMINI_API_KEY` | No | Direct Gemini access |
| `JWT_SECRET` | Prod | Secret for JWT token signing (required in production) |
| `GITHUB_CLIENT_ID` | No | GitHub OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | No | GitHub OAuth app client secret |
| `GOOGLE_CLIENT_ID` | No | Google OAuth app client ID |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth app client secret |
| `FRONTEND_URL` | No | Frontend URL for OAuth redirects (default: `http://localhost:3000`) |
| `BACKEND_URL` | No | Backend URL for OAuth callbacks (default: `http://localhost:8000`) |
| `DATABASE_URL` | No | PostgreSQL connection string (uses SQLite if not set) |
| `DATABASE_PATH` | No | SQLite database path (default: `company.db`) |
| `REDIS_URL` | No | Redis connection string |
| `SMART_MODEL` | No | Default smart model (default: `openrouter/free`) |
| `FALLBACK_MODEL` | No | Default fallback model (default: `openrouter/free`) |
| `N8N_WEBHOOK_URL` | No | n8n webhook for sharing |

## Multi-Key Setup (Recommended)

For best performance, configure 6 OpenRouter API keys — one per agent:

```env
OPENROUTER_API_KEY=sk-or-v1-key1
OPENROUTER_API_KEY_2=sk-or-v1-key2
OPENROUTER_API_KEY_3=sk-or-v1-key3
OPENROUTER_API_KEY_4=sk-or-v1-key4
OPENROUTER_API_KEY_5=sk-or-v1-key5
OPENROUTER_API_KEY_6=sk-or-v1-key6
```

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Email/password login |
| GET | `/api/auth/me` | Get current user |
| GET | `/api/auth/providers` | List enabled OAuth providers |
| GET | `/api/auth/github` | Start GitHub OAuth flow |
| GET | `/api/auth/google` | Start Google OAuth flow |

### Projects
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects` | Create new project |
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/{id}` | Get project state |
| DELETE | `/api/projects/{id}` | Delete project |
| POST | `/api/projects/{id}/approve/{output_id}` | Approve/reject agent output |
| POST | `/api/projects/{id}/revise` | Request agent revision |

### Agent Interaction
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects/{id}/call` | Chat with an agent |
| POST | `/api/projects/{id}/call/stream` | Streaming agent chat |
| GET | `/api/projects/{id}/conversation/{role}` | Get conversation history |
| POST | `/api/classify` | Classify input into pipeline route |

### Downloads & Deliverables
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/download/code` | Download generated code (.zip) |
| GET | `/api/projects/{id}/download/pptx` | Download presentation |
| GET | `/api/projects/{id}/download/docx` | Download report |
| GET | `/api/projects/{id}/download/workflow` | Download n8n workflow |

### Code Preview & GitHub
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/{id}/files` | List generated files |
| GET | `/api/projects/{id}/preview` | Start live code preview |
| POST | `/api/projects/{id}/push-to-github` | Push code to GitHub |
| POST | `/api/settings/github-token` | Save GitHub token |

### Sharing
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects/{id}/share-link` | Create shareable link |
| GET | `/api/shared/{token}` | View shared project |

### Real-time
| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/api/ws/{id}` | Real-time project updates |

## License

MIT
