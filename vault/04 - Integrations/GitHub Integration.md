# GitHub Integration

#integration #deploy #live

> Auto-deploy the AI Software Company platform. Frontend on Vercel, backend on Railway — both auto-deploy from GitHub.

## Status: `Live` — deployed 2026-08-11

## What's Deployed

| Service | Platform | URL | Auto-deploy |
|---------|----------|-----|-------------|
| **Frontend** | Vercel | [frontend-wheat-ten-gla6y29t60.vercel.app](https://frontend-wheat-ten-gla6y29t60.vercel.app) | Yes (git push) |
| **Backend** | Railway | [ai-software-company-production.up.railway.app](https://ai-software-company-production.up.railway.app) | CLI deploy |

## Vercel Setup (Frontend)

- **Root Directory:** `frontend` (set in Build and Deployment settings)
- **Framework:** Next.js (auto-detected)
- **Environment Variables:**
  - `NEXT_PUBLIC_API_URL` = `https://ai-software-company-production.up.railway.app/api`
  - `NEXT_PUBLIC_WS_URL` = `wss://ai-software-company-production.up.railway.app/api`
- **Auto-deploy:** Triggers on every push to `master` branch

## Railway Setup (Backend)

- **Project name:** `elegant-kindness`
- **Root Directory:** Deployed via CLI with `--path-as-root` flag
- **Runtime:** Python 3.11.9
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` (from Procfile)
- **Health check:** `GET /health` returns `{"status": "ok"}`

### Railway Environment Variables

```env
OPENROUTER_API_KEY=sk-or-v1-...
TAVILY_API_KEY=tvly-dev-...
FRONTEND_URL=https://frontend-wheat-ten-gla6y29t60.vercel.app
SMART_MODEL=google/gemma-3-27b-it:free
MODEL_CEO=google/gemma-3-27b-it:free
MODEL_BA=google/gemma-3-27b-it:free
MODEL_RESEARCHER=google/gemma-3-27b-it:free
MODEL_ARCHITECT=deepseek/deepseek-chat-v3-0324:free
MODEL_ENGINEER=anthropic/claude-sonnet-4
MODEL_PPT=google/gemma-3-27b-it:free
MODEL_REVIEW=google/gemma-3-27b-it:free
FALLBACK_MODEL=google/gemini-2.5-flash
MISE_PYTHON_GITHUB_ATTESTATIONS=false
```

### Railway CLI Commands

```bash
# Deploy backend
npx @railway/cli up ./backend --path-as-root --detach

# Check status
npx @railway/cli service status

# View logs
npx @railway/cli service logs

# Set environment variable
npx @railway/cli variables set KEY=value
```

## CORS Configuration

Backend allows:
- `http://localhost:3000` and `http://localhost:3001` (local dev)
- Any `*.vercel.app` domain (regex match)
- Explicit `FRONTEND_URL` from env var

## GitHub Student Developer Pack

Approved 2026-08-11. Provides:
- Vercel Pro (free with Student Pack)
- Railway credits ($5/month)
- GitHub Actions (2,000 min/month)
- Namecheap free .me domain

## Build Notes

- Railway required `MISE_PYTHON_GITHUB_ATTESTATIONS=false` to bypass Python 3.11.9 attestation check failure in their builder
- Vercel required Root Directory set to `frontend` under Build and Deployment settings (not General)

---

Related: [[Tech Stack]], [[Orchestrator]], [[Engineer Agent]], [[Model Strategy]]
