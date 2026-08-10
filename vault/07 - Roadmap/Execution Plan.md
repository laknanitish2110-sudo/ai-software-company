# Execution Plan

Day-by-day plan from [[Gap Analysis]]. Split into what we can do NOW (no GitHub needed) vs. what needs the Student Developer Pack.

---

## Today — Aug 9 (No GitHub Needed)

These require zero external dependencies. Just code.

### 1. Split Model Strategy (30 min) — Gap 2

> [!pipeline] Update `.env` with per-agent models
> | Agent | Model | Cost |
> |-------|-------|------|
> | CEO | `google/gemma-3-27b-it:free` | Free |
> | BA | `google/gemma-3-27b-it:free` | Free |
> | Researcher | `google/gemma-3-27b-it:free` | Free |
> | Architect | `deepseek/deepseek-chat-v3-0324:free` | Free |
> | Engineer | `anthropic/claude-sonnet-4` | ~$0.25 |
> | PPT | `google/gemma-3-27b-it:free` | Free |
> | Cross-review | `google/gemma-3-27b-it:free` | Free |
>
> **Files:** `backend/.env`
> **Verify:** Run one pipeline, check each agent uses the right model

### 2. Retry Logic & Error Handling (2-3 hrs) — Gap 1

> [!code] Add resilience to `engine.py`
> - 3 retries with exponential backoff (2s, 4s, 8s)
> - JSON repair: strip markdown fences, fix common LLM JSON errors
> - Per-agent timeouts: CEO 60s, BA/Researcher 120s, Architect 90s, Engineer 300s
> - If cross-review fails, skip and continue (non-critical)
> - Log all failures to memory for debugging
>
> **Files:** `backend/app/agents/engine.py`

### 3. Streaming Agent Output (3-4 hrs) — Gap 4

> [!code] Stream tokens to frontend via WebSocket
> - Switch `client.chat.completions.create()` to `stream=True`
> - Forward each chunk via WebSocket: `{"type": "agent_stream", "token": "..."}`
> - Frontend shows live text appearing + token counter
> - Show elapsed time per agent
>
> **Files:** `backend/app/agents/engine.py`, `backend/app/api/routes.py`, `frontend/src/components/AgentOutput.tsx`

### 4. Demo Fallback / Replay Mode (2-3 hrs) — Gap 3

> [!pipeline] Cache a successful run for instant replay
> - After a successful pipeline: export all outputs to `backend/demo_cache/`
> - New API endpoint: `POST /api/projects/demo` loads cached outputs
> - Frontend "Demo Mode" button on the start page
> - Simulated timing (show agents "working" for 3-5s each, then reveal cached output)
>
> **Files:** New `backend/app/services/demo_cache.py`, `backend/app/api/routes.py`, `frontend/src/components/StartProject.tsx`

---

## Tomorrow — Aug 10 (With GitHub Student Dev Pack)

### 5. GitHub Integration (2-3 days) — Gap 7 + Level 4

> [!code] The big one. Full auto-deploy pipeline.
> - `github.py`: Create repo, push Engineer's generated files
> - GitHub Actions: Auto-build on push
> - `deployer.py`: Trigger Vercel deploy, return live URL
> - Wire into [[Orchestrator]]: after Engineer approval → auto-deploy
> - Auto-fix loop: build fails → Engineer gets error → fixes → redeploy
>
> See [[GitHub Integration]] for the full architecture.
>
> **Files:** New `backend/app/services/github.py`, `backend/app/services/deployer.py`, `backend/app/services/build_monitor.py`, update `orchestrator.py`

### 6. API Key Failover (1 hr) — Gap 8

> [!status] Add backup providers
> - Second OpenRouter API key in `.env` as `OPENROUTER_API_KEY_BACKUP`
> - Failover logic in `engine.py`: if primary fails, try backup
> - Direct Anthropic key for Claude Sonnet 4 as last resort
> - Get OmniRoute working as middleware layer
>
> **Files:** `backend/.env`, `backend/app/core/config.py`, `backend/app/agents/engine.py`

---

## Aug 11-14 (Polish Week)

### 7. Live Agent Canvas (1-2 days) — Gap 6 + Gap 9

> [!agent] The money shot for LaunchpadX
> - New React component: `AgentCanvas.tsx`
> - Animated agent nodes on a dark canvas
> - Data flow lines between agents
> - Real-time token counters
> - Cross-review arrows
> - Integrates with existing WebSocket events
>
> **Files:** New `frontend/src/components/AgentCanvas.tsx`, update `frontend/src/app/project/[id]/page.tsx`

### 8. Better PPT Templates (3-4 hrs) — Gap 5

> [!pipeline] Professional slide design
> - Dark theme matching the Obsidian vault style
> - Title slide with project name, team, date, logo
> - Architecture diagram slide
> - Tech stack slide
> - "How it works" flow slide
> - Better fonts, colors, spacing
>
> **Files:** `backend/app/services/pptx_generator.py`

### 9. Agent Introspection Panel (3-4 hrs) — Gap 11

> [!agent] Click any agent → see its full context
> - New component or modal in AgentOutput
> - Shows: input context, model used, time taken, token count, peer review
> - Syntax-highlighted raw output
>
> **Files:** `frontend/src/components/AgentOutput.tsx`

---

## Aug 15-17 (Demo Prep)

### 10. Demo Script & Practice (2 hrs) — Gap 10

> [!decision] Write and rehearse the 5-minute pitch
> - Pick the best SIH problem statement for the demo
> - Script every step (what to click, what to say)
> - Prepare for "what if it fails" (demo fallback)
> - Practice 10 times
> - Time yourself

### 11. Unique Output Demo (1 hr) — Gap 12

> [!decision] Show differentiation
> - Run same problem twice with different approval feedback
> - Screenshot both outputs side-by-side
> - Add to presentation: "Same input, different steering, unique output"

### 12. Final Testing (2-3 hrs)

> [!status] Full pipeline test x3
> - Test with 3 different SIH problem statements
> - Verify all deliverables (ZIP, PPTX, DOCX)
> - Test demo fallback mode
> - Test with spotty internet (mobile hotspot)
> - Load test: submit 2 projects simultaneously

---

## Summary

> [!pipeline] Time Budget
> | Phase | Days | Items |
> |-------|------|-------|
> | **Today (Aug 9)** | 1 | Model strategy, retry logic, streaming, demo cache |
> | **Tomorrow (Aug 10)** | 1 | GitHub integration starts, failover |
> | **Build (Aug 11-14)** | 4 | GitHub complete, Agent Canvas, PPT, introspection |
> | **Polish (Aug 15-17)** | 3 | Demo script, testing, unique output demo |
> | **SIH (Aug 18-19)** | 2 | Hackathon #1 |
> | **Adapt (Aug 20-21)** | 2 | Fix issues, adapt pitch for LaunchpadX |
> | **LaunchpadX (Aug 22-23)** | 2 | Hackathon #2 |

---

Related: [[Gap Analysis]], [[Roadmap]], [[GitHub Integration]], [[Model Strategy]], [[Pipeline Flow]], [[LaunchpadX]]

#roadmap #execution #plan
