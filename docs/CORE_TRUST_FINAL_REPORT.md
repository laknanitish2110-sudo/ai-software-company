# Core Trust Gate v1 — Final Report

Completed: 2026-09-06

## Summary

The Core Trust hardening phase moved production readiness from ~6.5/10 to ~8.5/10 across security, reliability, and deployment transparency — without adding new features or changing the product architecture.

## What Was Done

### Security (6.5 → 8.5)

| Item | Commit | Impact |
|------|--------|--------|
| Domain memory tenant isolation | `7826a8a` | Users can only query learnings from their own projects. JOIN through `projects` table filters by `user_id`. |
| Static preview authorization | `3335cd6` | Preview endpoint requires auth + project ownership. CSP headers added. |
| Classify endpoint auth | `3335cd6` | No longer accessible without login. |
| Demo/load ownership | `3335cd6` | Demo projects properly assigned to authenticated user. |
| Path traversal prevention | `3d39cb8` | Unified `_is_safe_path()` using `Path.relative_to()` across all 3 file-write paths. |
| Apply Changes file/size limits | `3d39cb8` | 200 files max, 500KB per file, 50MB total payload. |
| GitHub token Fernet encryption | This session | Replaced XOR obfuscation with `cryptography.Fernet` (AES-128-CBC + HMAC-SHA256). Legacy XOR tokens auto-detected and decrypted for seamless migration. Supports dedicated `GITHUB_TOKEN_ENCRYPTION_KEY` env var. |
| Streaming error sanitization | This session | `call_employee_stream` no longer leaks raw exception strings to the client. Generic error message returned; full details logged server-side with `exc_info=True`. |
| System prompt hiding | Pre-existing | API returns `"system_prompt": "[hidden]"` — agent prompts never exposed to clients. |

### Reliability (7 → 8)

| Item | Commit | Impact |
|------|--------|--------|
| Apply Changes snapshot/rollback | This session | `shutil.copytree()` backup before mutation. On any failure, project directory is restored from snapshot. Backup cleaned up on success. |
| SecurityGate integration | `7e18634` + orchestrator | Runs after engineer completes. Non-blocking (informational) — stores results in memory, notifies frontend via WebSocket. |

### Deployment Transparency (6 → 8)

| Item | File | Impact |
|------|------|--------|
| Deployment truth | `docs/DEPLOYMENT_TRUTH.md` | Documents actual topology, what survives restarts, critical env vars, single-instance boundary. |
| Sandbox limitations | `docs/SANDBOX_LIMITATIONS.md` | Documents in-memory tracking as intentional MVP decision, accepted tradeoffs, when to revisit. |
| Security audit | `docs/CORE_TRUST_AUDIT.md` | Full authorization matrix for all endpoints, 7 prioritized findings. |

### Test Coverage

| Suite | Tests | File |
|-------|-------|------|
| Security hardening | 16 | `tests/test_security_hardening.py` |
| Route/revision invariants | 16 | `tests/test_route_revision_invariants.py` |
| **Total new tests** | **32** | |

Coverage areas: path traversal (10 cases), file limits (2), domain memory isolation (2), endpoint auth (2), pipeline route configs (6), revision context (3), Fernet encryption (4), streaming sanitization (1), apply snapshot (2).

## What Was NOT Changed (by design)

- Core agent pipeline architecture
- Agent Canvas / Build Room concept
- Company/workforce metaphor
- Provider abstraction and model routing
- Approval flow and task routing
- Existing UI and UX patterns
- No new agents, no new features

## Known Accepted Limitations

1. **SecurityGate is informational, not blocking** — A project with critical security findings can still be approved and pushed to GitHub. Blocking would change user workflow and was deferred.
2. **Sandbox tracking is in-memory** — Accepted for single-instance MVP. See `SANDBOX_LIMITATIONS.md`.
3. **GitHub push uses `force: true` on ref update** — Only for initial commit when ref already exists (e.g., from `auto_init`). No force-push on subsequent pushes.
4. **Rate limiter state is in-memory** — Resets on server restart. Acceptable for current scale.
5. **SQLite for projects** — Single-writer constraint is fine for single-instance. Would need PostgreSQL migration for horizontal scaling.

## Remaining Opportunities (Post-Trust Gate)

These are improvements that could be done incrementally without a dedicated hardening phase:
- Re-encrypt existing XOR tokens to Fernet on next user login (currently happens on next token save)
- Add per-user sandbox count limits
- Move rate limiter state to Redis for persistence across restarts
- SecurityGate blocking mode (opt-in, with UI toggle)
