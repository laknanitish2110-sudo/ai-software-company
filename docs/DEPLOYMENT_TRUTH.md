# Deployment Truth

Last verified: 2026-09-06

## Architecture

```
[Vercel]                    [Railway]
Next.js Frontend  ------>   FastAPI Backend
                            |       |       |
                         [Redis]  [Postgres]  [E2B Cloud]
                         (queue)  (users,     (code sandbox)
                                   projects)
```

## Services

| Component | Host | URL | Notes |
|-----------|------|-----|-------|
| Frontend | Vercel | ai-software-company-gold.vercel.app | Auto-deploy from `master` |
| Backend | Railway | railway app service | Auto-deploy from `master` |
| Redis | Railway | internal service | Used for task queue (arq) and pub/sub |
| PostgreSQL | Railway | internal service | Users, settings, task queue |
| SQLite | Railway filesystem | `data/projects.db` | Projects, outputs, memory, domain learnings |
| E2B Sandbox | E2B Cloud | per-session URLs | Code execution, live preview |

## What Survives a Restart

| Data | Storage | Survives Restart? |
|------|---------|-------------------|
| User accounts | PostgreSQL | Yes |
| User settings (GitHub tokens) | PostgreSQL | Yes |
| Projects, outputs, memory | SQLite file | Yes (if volume mounted) |
| Domain learnings | SQLite file | Yes (if volume mounted) |
| Generated project files | Filesystem (`generated_projects/`) | Yes (if volume mounted) |
| Active sandbox sessions | In-memory dict (`SandboxManager._active`) | **No** |
| WebSocket connections | In-memory set | **No** |
| Rate limiter state | In-memory dict | **No** |
| Task queue jobs | Redis | Yes (while Redis persists) |

## Critical Environment Variables

The backend requires these in `.env` (never commit):
- `NVIDIA_API_KEY` / `NVIDIA_API_KEY_2` — LLM provider
- `OPENROUTER_API_KEY` — LLM fallback provider
- `E2B_API_KEY` — code sandbox
- `JWT_SECRET` — auth token signing
- `GITHUB_CLIENT_SECRET` — OAuth
- `GOOGLE_CLIENT_SECRET` — OAuth
- `GITHUB_TOKEN_ENCRYPTION_KEY` — (optional) dedicated Fernet key for GitHub token encryption; falls back to derived key from JWT_SECRET

## Single-Instance Boundary

The backend runs as a single process. This means:
- In-memory state (sandbox tracking, WebSocket connections, rate limits) is not shared across instances
- SQLite works because there's one writer
- Scaling to multiple instances would require migrating SQLite to PostgreSQL and sandbox tracking to Redis

This is acceptable for the current user base (<100 users). See `SANDBOX_LIMITATIONS.md` for sandbox-specific constraints.

## Deploy Process

1. Push to `master` branch on GitHub
2. Vercel auto-deploys frontend (build: `npm run build`)
3. Railway auto-deploys backend (build: `pip install -r requirements.txt`, start: `uvicorn app.main:app`)
4. No manual steps required
