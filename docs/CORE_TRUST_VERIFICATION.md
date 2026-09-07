# Core Trust Gate v1 — Independent Verification Report

**Verification Date**: 2026-09-06
**Verifier**: Claude (read-only audit — no code modified during verification)
**Scope**: All claims made in Core Trust Gate v1 documentation and commits
**Method**: Source code inspection, git history analysis, test execution, cross-referencing

---

## 1. Repository Verification

| Check | Status | Evidence |
|-------|--------|----------|
| Working tree clean | **PASS** | `git status` shows clean tree, no uncommitted changes |
| Local matches remote | **PASS** | Both HEAD and origin/master at `bd06e82` |
| All 6 trust commits present | **PASS** | `git merge-base --is-ancestor` confirmed for all: `7826a8a`, `3335cd6`, `3d39cb8`, `05538c0`, `4e5c24e`, `bd06e82` |
| Commit chain unbroken | **PASS** | Linear history from `e964c45` (audit doc) through `bd06e82` (final) |
| No force-push evidence | **PASS** | `git log --oneline -10` shows clean linear progression |

---

## 2. Security Verification

### 2.1 Domain Memory Tenant Isolation

| Check | Status | Evidence |
|-------|--------|----------|
| SQL JOIN enforces user_id | **PASS** | `database.py:799` — `p.user_id = ?` appended to WHERE clause via JOIN through projects table |
| user_id parameter threaded through | **PASS** | `domain_memory.py` accepts `user_id`, passes to `query_domain_learnings()` |
| No bypass path | **PASS** | All callers of `get_relevant_learnings()` pass authenticated `user_id` |

**Commit**: `7826a8a`

### 2.2 Static Preview Authorization

| Check | Status | Evidence |
|-------|--------|----------|
| Auth required on preview endpoint | **PASS** | `routes.py` — `serve_static_preview` has `current_user` dependency |
| Ownership verified | **PASS** | `_verify_project_owner` called before serving files (30 total occurrences across routes.py) |
| Classify endpoint protected | **PASS** | Same auth pattern applied |
| Demo/load ownership | **PASS** | Demo projects assigned to authenticated user |

**Commit**: `3335cd6`

### 2.3 Path Traversal Prevention

| Check | Status | Evidence |
|-------|--------|----------|
| Unified `_is_safe_path()` exists | **PASS** | `file_generator.py:184-194` — backslash normalization, `..` component check, `Path.relative_to()` resolution |
| Used in `generate_project_files()` | **PASS** | `file_generator.py:30` |
| Used in `generate_deployable_bundle()` | **PASS** | `file_generator.py:156` |
| Used in `apply_file_updates()` | **PASS** | `file_generator.py:227` |
| Double protection (string + resolve) | **PASS** | Checks `..` in split path segments AND uses `.resolve()` + `.relative_to()` |

**Commit**: `3d39cb8`

### 2.4 Apply Changes File/Size Limits

| Check | Status | Evidence |
|-------|--------|----------|
| MAX_APPLY_FILES = 200 | **PASS** | `file_generator.py:179` |
| MAX_APPLY_FILE_SIZE = 500KB | **PASS** | `file_generator.py:180` — `500 * 1024` |
| MAX_APPLY_TOTAL_SIZE = 50MB | **PASS** | `file_generator.py:181` — `50 * 1024 * 1024` |
| File count checked before processing | **PASS** | `file_generator.py:199` — early return with error |
| Per-file size enforced | **PASS** | `file_generator.py:234-236` — oversized files skipped |
| Total size enforced | **PASS** | `file_generator.py:239-240` — raises ValueError, triggers snapshot restore |

**Commit**: `3d39cb8`

### 2.5 GitHub Token Fernet Encryption

| Check | Status | Evidence |
|-------|--------|----------|
| Fernet import | **PASS** | `github_service.py` imports from `cryptography.fernet` |
| `FERNET_PREFIX = "fernet:"` | **PASS** | `github_service.py:14` |
| `obfuscate_token()` uses Fernet | **PASS** | `github_service.py:34-38` — `f.encrypt()` + prefix |
| `deobfuscate_token()` detects prefix | **PASS** | `github_service.py:41-46` — prefix detection routes to Fernet or legacy XOR |
| Legacy XOR migration path | **PASS** | `_xor_decrypt_legacy()` at line 24 handles old tokens transparently |
| Supports dedicated env var | **PASS** | `_get_fernet()` checks `GITHUB_TOKEN_ENCRYPTION_KEY` first, falls back to SHA-256 of JWT_SECRET |
| `cryptography` in requirements | **PASS** | `requirements.txt` includes `cryptography>=42.0.0` |

**Commit**: `4e5c24e`

### 2.6 Streaming Error Sanitization

| Check | Status | Evidence |
|-------|--------|----------|
| Generic error to client | **PASS** | `engine.py:803` — `'An error occurred while generating the response. Please try again.'` |
| Full trace to server logs | **PASS** | `engine.py:802` — `logger.error(... exc_info=True)` |
| No raw exception leak | **PASS** | Exception variable `e` only used in logger, not in SSE yield |

**Commit**: `4e5c24e`

### 2.7 System Prompt Hiding

| Check | Status | Evidence |
|-------|--------|----------|
| API returns `[hidden]` | **PASS** | `routes.py:625` — `"system_prompt": "[hidden]"` in introspection response |
| Actual prompts in `SYSTEM_PROMPTS` dict | **PASS** | `engine.py:78` — prompts defined server-side, never serialized to client |

**Pre-existing** (verified still intact)

### 2.8 SecurityGate Integration

| Check | Status | Evidence |
|-------|--------|----------|
| Import exists | **PASS** | `orchestrator.py:41` — `from app.services.security_gate import scan_files as security_scan_files` |
| Module exists | **PASS** | `security_gate.py:198` — `def scan_files(files: list[dict]) -> SecurityScanResult` |
| Called after engineer completes | **PASS** | `orchestrator.py:332` — `scan_result = security_scan_files(eng_files)` |
| Results stored in memory | **PASS** | `orchestrator.py:333` — `await set_memory(project_id, "security_scan", ...)` |
| Results notified to frontend | **PASS** | `orchestrator.py:337` — `await self._notify("security_scan", ...)` |
| Non-blocking (try/except) | **PASS** | `orchestrator.py:338-339` — `except Exception as sec_err: logger.warning(...)` |
| Informational only (not blocking) | **PASS** | Pipeline continues regardless of scan result |

**Commit**: `4e5c24e` (orchestrator integration); `security_gate.py` from prior work

### 2.9 GitHub Force Push Scope

| Check | Status | Evidence |
|-------|--------|----------|
| `force: True` location | **PARTIAL** | `github_service.py:132` — only in PATCH fallback when POST ref creation fails (status not 200/201) |
| Risk assessment | **PARTIAL** | This means force-push happens when the ref already exists (e.g., repo initialized with `auto_init`). After the first push, subsequent pushes would also use this PATCH path since the ref already exists. The `force: True` could overwrite concurrent manual commits to the same repo. |

**Accepted limitation** — documented in CORE_TRUST_FINAL_REPORT.md item #3

---

## 3. Reliability Verification

### 3.1 Apply Changes Snapshot/Rollback

| Check | Status | Evidence |
|-------|--------|----------|
| Backup created before writes | **PASS** | `file_generator.py:206-212` — `shutil.copytree(project_dir, backup_dir)` |
| Old backup cleaned first | **PASS** | `file_generator.py:208-209` — `if backup_dir.exists(): shutil.rmtree(backup_dir)` |
| Snapshot creation failure returns error | **PASS** | `file_generator.py:211-212` — `except OSError: return error` |
| Rollback on any write failure | **PASS** | `file_generator.py:251-254` — `shutil.rmtree(project_dir); shutil.move(backup_dir, project_dir)` |
| Backup cleaned on success | **PASS** | `file_generator.py:256` — `shutil.rmtree(backup_dir, ignore_errors=True)` |
| ZIP regenerated after writes | **PASS** | `file_generator.py:246-250` — inside same try block |

**Commit**: `4e5c24e`

### 3.2 Empty File Content Distinction

| Check | Status | Evidence |
|-------|--------|----------|
| Missing `content` key → skip | **PASS** | `file_generator.py:223-225` — `if "content" not in entry: skipped.append(path)` |
| Empty string content → write empty file | **PASS** | `file_generator.py:232-233` — `content = entry["content"]` then `encode()`, empty string produces `b""` which writes as empty file |
| Distinction is correct | **PASS** | `"content" not in entry` (no key) differs from `entry["content"] == ""` (empty value) |

**Commit**: `bd06e82`

### 3.3 Revision Context for Engineer Iteration

| Check | Status | Evidence |
|-------|--------|----------|
| `_build_existing_files_context()` exists | **PASS** | `engine.py:457-476` |
| Reads generated files from disk | **PASS** | Calls `get_generated_file_contents(project_id)` |
| Context heading correct | **PASS** | `"## Current Generated Files (modify these, don't regenerate from scratch)"` |
| Injected for engineer role only | **PASS** | `engine.py:516-522` — `if role == AgentRole.ENGINEER` |
| Size-capped at 60KB | **PASS** | `max_chars: int = 60000` parameter |

**Pre-existing** (verified still intact)

---

## 4. Test Verification

### 4.1 Test Execution Results

| Metric | Value |
|--------|-------|
| Total tests | 32 |
| Passed | 32 |
| Failed | 0 |
| Skipped | 0 |
| Test files | `test_security_hardening.py` (16), `test_route_revision_invariants.py` (16) |

**Status**: **PASS**

### 4.2 Test Coverage Map

| Area | Tests | Verified |
|------|-------|----------|
| Path traversal vectors | 10 | **PASS** — includes `../`, `..\\`, absolute paths, symlink-style, encoded dots |
| File count/size limits | 2 | **PASS** — exceeds count, exceeds per-file size |
| Domain memory isolation | 2 | **PASS** — user_id filtering confirmed |
| Endpoint auth presence | 2 | **PASS** — unauthenticated request returns 401/403 |
| Pipeline route configs | 6 | **PASS** — route keys, agent prompts, quick_build minimal, standard has architect, classify |
| Revision context | 3 | **PASS** — empty context, file formatting, prompt length |
| Fernet encryption | 4 | **PASS** — roundtrip, legacy migration, different ciphertexts, custom key |
| Streaming error sanitization | 1 | **PASS** — nonexistent project gets generic error, not stack trace |
| Apply snapshot/restore | 2 | **PASS** — backup cleanup on success, restore on total size overflow |

---

## 5. Deployment Verification

### 5.1 Code Push Status

| Check | Status | Evidence |
|-------|--------|----------|
| Local HEAD = origin/master | **PASS** | Both at `bd06e82dbbc5cad6802f3ae5614bdbd8f3fae060` |
| All trust commits pushed | **PASS** | Remote contains full commit chain |
| No unpushed changes | **PASS** | Clean working tree, no commits ahead |

### 5.2 Dependency Deployment

| Check | Status | Evidence |
|-------|--------|----------|
| `cryptography>=42.0.0` in requirements.txt | **PASS** | Verified in file |
| `GITHUB_TOKEN_ENCRYPTION_KEY` env var documented | **PASS** | `DEPLOYMENT_TRUTH.md` lists it |
| `NEXT_PUBLIC_API_URL` configured for frontend | **PASS** | Vercel env var references Railway backend URL |

### 5.3 Live Deployment Health

| Check | Status | Evidence |
|-------|--------|----------|
| Backend responds on Railway | **UNVERIFIED** | Cannot reach live endpoint from this verification context. Auto-deploy from master is configured, but actual deployment status not confirmed. |
| Frontend serves on Vercel | **UNVERIFIED** | Same — auto-deploy configured, not live-tested |
| Fernet encryption works with deployed env vars | **UNVERIFIED** | Requires live token encrypt/decrypt cycle |

### 5.4 Documentation Completeness

| Document | Exists | Content Verified |
|----------|--------|-----------------|
| `docs/CORE_TRUST_AUDIT.md` | **PASS** | Authorization matrix + 7 findings |
| `docs/DEPLOYMENT_TRUTH.md` | **PASS** | Topology, restart survival, env vars, single-instance boundary |
| `docs/SANDBOX_LIMITATIONS.md` | **PASS** | In-memory tracking, accepted tradeoffs, when to revisit |
| `docs/CORE_TRUST_FINAL_REPORT.md` | **PASS** | All items match verified code state |
| `docs/CORE_TRUST_IMPLEMENTATION_PLAN.md` | **PASS** | Day-by-day log matches commit history |
| `docs/TRUST_SMOKE_TEST.md` | **N/A** | Deferred by user — not part of hardening scope |

---

## 6. Cross-Reference: Final Report Claims vs Code

Every claim in `CORE_TRUST_FINAL_REPORT.md` was verified against source code:

| Claim | Code Match |
|-------|------------|
| Domain memory JOIN by user_id | `database.py:799` — confirmed |
| Static preview requires auth + ownership | `routes.py` — 30 occurrences of `_verify_project_owner` |
| Unified `_is_safe_path()` across 3 paths | `file_generator.py:30,156,227` — confirmed |
| 200/500KB/50MB limits | `file_generator.py:179-181` — confirmed |
| Fernet replacing XOR | `github_service.py:14-46` — confirmed |
| Streaming generic error | `engine.py:801-803` — confirmed |
| `"system_prompt": "[hidden]"` | `routes.py:625` — confirmed |
| Snapshot before mutation | `file_generator.py:206-212` — confirmed |
| SecurityGate non-blocking | `orchestrator.py:338-339` — confirmed |
| 32 tests, 0 failures | Test execution — confirmed |

**All claims verified. No discrepancies found.**

---

## 7. Known Accepted Limitations

These are documented, intentional decisions — not failures:

1. **SecurityGate is informational, not blocking** — scans run, results stored and notified, but pipeline does not halt on findings
2. **Sandbox tracking in-memory** — `SandboxManager._active` is a Python dict; lost on restart (documented in `SANDBOX_LIMITATIONS.md`)
3. **GitHub `force: true` on ref update** — used when ref already exists (PATCH fallback). Could overwrite concurrent manual commits. Acceptable for MVP where repos are auto-created.
4. **Rate limiter in-memory** — resets on server restart. No persistence to Redis.
5. **SQLite for project data** — single-writer constraint acceptable for single-instance deployment

---

## 8. Items Not Verified (Out of Scope)

| Item | Reason |
|------|--------|
| Live deployment health (backend/frontend responding) | Verification context cannot reach deployed URLs |
| Fernet encryption with production env vars | Requires live encrypt/decrypt with actual Railway env |
| 5-problem smoke test | Deferred by user ("LETS DO THE TEST LATER") |
| WebSocket connection stability | Requires live multi-user testing |
| E2B sandbox lifecycle under load | Requires live sandbox creation |

---

## 9. Final Classification

### **SHIP-READY WITH KNOWN LIMITATIONS**

**Rationale**:

- **Security**: All 8 security items verified as implemented and working in code. Path traversal blocked by dual-layer protection. Tenant isolation enforced by SQL JOIN. Encryption upgraded from XOR to Fernet with legacy migration. No raw exceptions leak to clients.

- **Reliability**: Snapshot/rollback protects against write failures. File limits prevent resource exhaustion. SecurityGate provides post-generation scanning.

- **Tests**: 32/32 passing. Coverage spans all critical security and reliability paths.

- **Documentation**: 5/5 required documents exist and accurately describe the system.

- **Deployment**: Code fully pushed. Auto-deploy configured. Live health **unverified** from this context.

**Why not SHIP-READY (unconditional)**:
1. Live deployment health was not confirmed
2. 5-problem smoke test is still pending
3. `force: true` on GitHub ref update is a known risk for repos with concurrent manual commits

**Why not NOT SHIP-READY**:
Every security and reliability claim was verified against actual source code. All tests pass. All documentation is accurate. The known limitations are intentional MVP decisions, not bugs or missing implementations. The unverified items are operational checks, not code defects.

**Recommendation**: Run the deferred 5-problem smoke test against the live site. If the backend health check returns 200 and the smoke test passes, upgrade classification to **SHIP-READY**.
