# Core Trust Audit — AI Software Company

**Date:** 2026-09-06
**Branch:** master (commit ee5fe9b)
**Auditor:** Claude (CTO role)

---

## 1. Architecture Overview

### Product Loop
```
Founder → CEO → BA → Researcher → Architect → Engineer → QA/Repair → Generated Software → Preview/Download/GitHub → Founder Iteration
```

### Backend Stack
- FastAPI + Uvicorn
- SQLite (dev) / PostgreSQL (prod)
- Redis (execution coordination, distributed locks)
- E2B (sandbox execution)
- OpenRouter / NVIDIA / Groq / OpenAI / Anthropic / Gemini (LLM providers)

### Frontend Stack
- Next.js (App Router)
- Deployed on Vercel

### Deployment
- Frontend: Vercel (ai-software-company-gold.vercel.app)
- Backend: Railway (3 services: app + Redis + Postgres)
- Auto-deploy from GitHub push to master

---

## 2. Authentication Model

**Implementation:** `backend/app/core/auth.py`

- Password hashing: PBKDF2-HMAC-SHA256, 100k iterations, 16-byte salt — **solid**
- JWT: HS256, 24-hour expiry, claims: sub/email/exp/iat
- JWT secret enforces minimum 16 chars, rejects known-insecure defaults in production
- `get_current_user`: extracts bearer token → decodes JWT → looks up user by ID
- OAuth: GitHub + Google callback flows

**Verdict: Adequate for current stage.**

---

## 3. Authorization Model

**Implementation:** `backend/app/api/routes.py`

- `_verify_project_owner(project_id, user_id)` → calls `get_project_for_user` which queries `WHERE id = ? AND user_id = ?`
- Authorization is enforced at the route layer, not the database layer
- This is acceptable IF all routes consistently call the check

### Authorization Matrix

| Endpoint | Auth | Owner Check | Status |
|----------|------|-------------|--------|
| Project CRUD | Yes | Yes | OK |
| Agent outputs | Yes | Yes | OK |
| Approve/reject | Yes | Yes | OK |
| Call employee | Yes | Yes | OK |
| Apply file changes | Yes | Yes | OK |
| GitHub push | Yes | Yes | OK |
| Download code | Yes | Yes | OK |
| WebSocket | Yes (JWT in query) | Yes | OK |
| Share link access | No (token-based) | N/A | OK by design |
| **Static preview** | **No** | **No** | **BUG** |
| **POST /classify** | **No** | **N/A** | **RISK** |
| **GET /domain-learnings** | **Yes** | **No tenant filter** | **BUG** |
| **GET /demo/load** | **Yes** | **Creates orphan** | **BUG** |

---

## 4. Findings

### FINDING 1: Cross-Tenant Domain Memory Leakage [P0 — CRITICAL]

**Files:** `domain_memory.py:195`, `database.py:785`

**Problem:** `get_relevant_learnings()` queries the `domain_learnings` table globally. The table has no `user_id` column. Any authenticated user's domain learnings can be surfaced to any other user.

**Impact:** Private project details (architecture decisions, technology choices, business logic) leak across users.

**Fix:** Add `user_id` column to `domain_learnings` table. Filter queries by user_id. Decide which learnings are global vs. private.

**Severity:** Critical — privacy violation

---

### FINDING 2: Unauthenticated Static Preview [P0 — HIGH]

**File:** `routes.py:741`

**Problem:** `GET /projects/{project_id}/preview/static` serves the generated `index.html` without any authentication or authorization check. Anyone with a project ID can view the output.

**Impact:** Generated code exposed to unauthenticated access. Project IDs are 16-hex-char (64-bit entropy) — not brute-forceable, but shareable/leakable.

**Fix:** Add `Depends(get_current_user)` + `_verify_project_owner`, OR implement explicit share-token semantics for intentionally public previews.

**Severity:** High — data exposure

---

### FINDING 3: No File Size/Count Limits on Apply Changes [P2 — MEDIUM]

**File:** `file_generator.py:195`

**Problem:** `apply_file_updates()` accepts unbounded file count and content size. No per-file or total payload limits. A malicious or malformed engineer response could write gigabytes to disk.

**Current path validation:** String-prefix check (`str(full_path).startswith(str(resolved_root))`) — functional but less robust than `is_relative_to()`.

**Fix:** Add limits (max 200 files, 500KB per file, 50MB total). Upgrade path validation to `is_relative_to()` consistently.

**Severity:** Medium — DoS vector, no data exposure

---

### FINDING 4: Weak GitHub Token Storage [P4 — MEDIUM]

**File:** `github_service.py:17`

**Problem:** XOR obfuscation with SHA-256 of JWT_SECRET. Not encryption. Trivially reversible by anyone with the JWT secret.

**Impact:** In dev mode, JWT_SECRET has a known default value. In production, the JWT secret is reused as the encryption key (violates key separation).

**Fix:** Replace with `cryptography.Fernet` (AES-CBC + HMAC). Use a dedicated `GITHUB_ENCRYPTION_KEY` env var. Migrate existing tokens.

**Severity:** Medium — requires server access to exploit

---

### FINDING 5: Unauthenticated Classify Endpoint [P5 — LOW]

**File:** `routes.py:368`

**Problem:** `POST /classify` processes a problem statement without authentication. If it makes an LLM call internally, this enables unauthenticated LLM spend.

**Fix:** Add `Depends(get_current_user)`.

**Severity:** Low — cost risk only

---

### FINDING 6: Demo/Load Creates Orphaned Projects [P1 — LOW]

**File:** `routes.py:1038`

**Problem:** `GET /demo/load` inserts a project without `user_id`, making it inaccessible through ownership-checked endpoints. Project gets `user_id = 'legacy_owner'`.

**Fix:** Assign `current_user["id"]` when restoring demo projects.

**Severity:** Low — broken functionality, not security

---

### FINDING 7: In-Memory Sandbox Tracking [P3 — ACCEPTED]

**File:** `sandbox_manager.py:15`

**Problem:** Sandbox handles stored in process-local dict. Server restart loses all references; E2B sandboxes leak until E2B's own timeout.

**Impact:** Operational cost (leaked sandboxes bill until E2B kills them). Not exploitable.

**Decision:** Accept for single-instance MVP. Document as architectural boundary.

---

## 5. What's Already Solid

- WebSocket auth: properly validates JWT + project ownership
- Project CRUD: consistently uses `_verify_project_owner`
- Password hashing: industry-standard PBKDF2
- JWT: rejects insecure defaults in production, enforces minimum key length
- Path traversal protection: present in both `generate_project_files` and `apply_file_updates`
- Rate limiting: exists for project creation and API calls
- Execution locks: Redis-based distributed locking prevents duplicate agent runs
- Agent introspection: system prompts hidden from API (`[hidden]`)
- Existing test suite: 25+ test files covering auth, sandbox, repair, execution, models

---

## 6. Implementation Priority

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| P0-1 | Domain memory tenant isolation | 1-2 hours | Fixes privacy leak |
| P0-2 | Static preview auth | 30 min | Fixes data exposure |
| P2-1 | Apply Changes limits + path validation | 1 hour | Prevents DoS |
| P4-1 | GitHub token Fernet encryption | 1-2 hours | Proper crypto |
| P5-1 | Classify endpoint auth | 5 min | Prevents free LLM use |
| P1-1 | Demo/load ownership fix | 15 min | Fixes broken feature |

**Total estimated effort: 4-6 hours**
