# Sandbox Limitations (MVP)

Last verified: 2026-09-06

## Architecture

Sandboxes are E2B cloud instances used for:
- Running generated code to verify it works
- Serving live preview URLs for generated web apps
- Executing repair loop iterations (build → test → fix)

## In-Memory Tracking

`SandboxManager` (`backend/app/services/sandbox_manager.py`) tracks active sandboxes in a Python dict (`self._active`). This means:

- **Server restart kills all active previews** — sandbox IDs are lost, no reconnection possible
- **No persistence** — there is no database record of which sandboxes are running
- **Auto-cleanup** — each sandbox has a configurable timeout (`SANDBOX_PREVIEW_TIMEOUT`, default 600s) after which it's automatically killed
- **Single-instance only** — if the backend were scaled to multiple instances, each would have its own sandbox registry with no visibility into the others

## Accepted Tradeoffs

These are **intentional MVP decisions**, not bugs:

1. **Lost previews on deploy**: When Railway auto-deploys a new backend version, active preview URLs become unreachable. Users must re-run the engineer to get a new preview. This is acceptable because deploys are infrequent and previews are transient.

2. **No sandbox resume**: If a user closes their browser and returns, the preview URL may still work (E2B keeps the sandbox alive for its TTL) but the backend won't know about it. The user can always download the ZIP or re-run.

3. **Resource cleanup is best-effort**: If `sandbox.kill()` fails (network error, E2B outage), the sandbox continues running until E2B's own TTL expires. This costs money but doesn't affect correctness.

4. **No concurrent sandbox limits per user**: A user could theoretically create many sandboxes by rapidly creating projects. E2B's own account limits provide a backstop; we don't enforce per-user limits.

## When to Revisit

Move sandbox tracking to Redis when:
- The backend needs horizontal scaling (multiple instances)
- Preview uptime becomes a paid feature
- Sandbox costs exceed budget due to leaked instances
