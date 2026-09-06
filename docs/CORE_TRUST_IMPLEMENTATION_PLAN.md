# Core Trust Gate v1 — Implementation Plan

Status: **COMPLETED** (2026-09-06)

## Approach

"Brutal 80/20" — 4-day focused plan targeting 80% of the trust improvement from the full spec, prioritizing items with the highest security impact and lowest blast radius.

Full spec estimated 2-3 weeks. This plan delivered ~8.5/10 production readiness in 4 focused days.

## Execution Log

### Day 1: Audit + Security Foundations

| Task | Planned | Actual | Commit |
|------|---------|--------|--------|
| Write security audit document | 2h | Done | `e964c45` |
| Domain memory tenant isolation | 1h | Done — JOIN through projects table, no schema migration | `7826a8a` |
| Static preview auth + ownership | 1h | Done — added `get_current_user` + `_verify_project_owner` | `3335cd6` |
| Classify endpoint auth | 30min | Done (bundled with above) | `3335cd6` |
| Demo/load ownership fix | 30min | Done (bundled with above) | `3335cd6` |

### Day 2: Apply Changes Safety + Deployment Truth

| Task | Planned | Actual | Commit |
|------|---------|--------|--------|
| Unified `_is_safe_path()` | 1h | Done — `Path.relative_to()` across all 3 write paths | `3d39cb8` |
| File count/size limits | 30min | Done — 200 files, 500KB/file, 50MB total | `3d39cb8` |
| Snapshot/rollback before mutation | 1h | Done — `shutil.copytree` backup, restore on failure | `4e5c24e` |
| `docs/DEPLOYMENT_TRUTH.md` | 1h | Done | `4e5c24e` |

### Day 3: Token Encryption + Error Sanitization

| Task | Planned | Actual | Commit |
|------|---------|--------|--------|
| GitHub token Fernet encryption | 2h | Done — `cryptography.Fernet`, legacy XOR auto-migration | `4e5c24e` |
| Dedicated `GITHUB_TOKEN_ENCRYPTION_KEY` env var | 30min | Done (bundled with above) | `4e5c24e` |
| Streaming error sanitization | 30min | Done — generic error to client, full trace to logs | `4e5c24e` |

### Day 4: Tests + Documentation + Final Report

| Task | Planned | Actual | Commit |
|------|---------|--------|--------|
| Security test suite (16 tests) | 2h | Done — path traversal, limits, isolation, auth | `05538c0` |
| Route/revision invariant tests (16 tests) | 2h | Done — routes, revision context, Fernet, streaming, snapshot | `4e5c24e` |
| `docs/SANDBOX_LIMITATIONS.md` | 30min | Done | `4e5c24e` |
| `docs/CORE_TRUST_FINAL_REPORT.md` | 1h | Done | `4e5c24e` |
| Empty file content distinction | 15min | Done | Post-4e5c24e |
| This document | 15min | Done | Post-4e5c24e |

## Items Deliberately Deferred

| Item | Reason |
|------|--------|
| 100-problem benchmark harness | Separate product initiative, not hardening |
| Complete artifact versioning system | Snapshot safety is sufficient for MVP |
| Distributed sandbox architecture | <100 users, single-instance is fine |
| SecurityGate blocking mode | Would change user workflow; kept informational |
| Rate limiter persistence to Redis | Acceptable to reset on restart at current scale |
| SQLite → PostgreSQL migration for projects | Only needed for horizontal scaling |

## Verification

- 32 automated tests, 0 failures
- All endpoints have auth requirements verified
- Path traversal blocked across 10 attack vectors
- Fernet encryption roundtrip verified with legacy migration
- Snapshot rollback verified under payload overflow
- No raw exceptions leak to streaming clients

## Files Changed (across all commits)

### Modified
- `backend/app/agents/engine.py` — streaming error sanitization, iteration context
- `backend/app/services/file_generator.py` — path validation, limits, snapshot, empty file fix
- `backend/app/services/github_service.py` — Fernet encryption replacing XOR
- `backend/app/services/domain_memory.py` — user_id passthrough
- `backend/app/services/orchestrator.py` — user_id in domain memory calls
- `backend/app/core/database.py` — user_id JOIN in domain learnings query
- `backend/app/api/routes.py` — auth on preview/classify, ownership on demo/load
- `backend/requirements.txt` — added `cryptography>=42.0.0`

### Created
- `backend/tests/test_security_hardening.py` — 16 tests
- `backend/tests/test_route_revision_invariants.py` — 16 tests
- `docs/CORE_TRUST_AUDIT.md` — authorization matrix + findings
- `docs/CORE_TRUST_FINAL_REPORT.md` — completion summary
- `docs/CORE_TRUST_IMPLEMENTATION_PLAN.md` — this document
- `docs/DEPLOYMENT_TRUTH.md` — deployment topology
- `docs/SANDBOX_LIMITATIONS.md` — MVP sandbox constraints
