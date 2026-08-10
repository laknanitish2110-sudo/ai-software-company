# Webhook System

The webhook system fires HTTP events to external services (primarily [[n8n Integration|n8n]]) at key moments in the pipeline. This enables notifications, logging, and external automation without coupling the core pipeline to any specific integration.

## Architecture

> [!code] Event-Driven Notifications
> ```
> Pipeline event occurs
>   → webhook.py builds payload
>     → httpx POST (async, non-blocking)
>       → n8n webhook endpoint
>         → n8n workflow triggers
>           → Slack, email, logging, etc.
> ```

**File:** `backend/app/services/webhook.py`
**HTTP Client:** httpx (async)
**Target:** Configurable URL from `.env` (`WEBHOOK_URL`)
**Default target:** [[n8n Integration|n8n instance]] at `srv1867770.hstgr.cloud`

## Event Types

Five webhook events cover the entire pipeline lifecycle:

| Event | Fired When | Purpose |
|-------|------------|---------|
| `agent_started` | An agent begins processing | Track pipeline progress |
| `agent_completed` | An agent finishes (before review) | Log agent output |
| `approval_needed` | A gate is reached, waiting for Founder | Notify Founder to review |
| `deliverables_ready` | Pipeline complete, files generated | Notify that project is ready |
| `error` | Any agent or system error | Alert on failures |

## Payload Structure

Every webhook event follows a consistent JSON structure:

```json
{
  "event_type": "agent_completed",
  "project_id": "uuid-here",
  "timestamp": "2026-08-09T14:30:00Z",
  "data": {
    "agent_role": "business_analyst",
    "agent_label": "Business Analyst",
    "status": "completed",
    "duration_seconds": 125,
    "output_summary": "Generated 8 functional requirements...",
    "pipeline_position": "2/6"
  }
}
```

### Event-Specific Payloads

| Event | Additional Fields |
|-------|-------------------|
| `agent_started` | `agent_role`, `pipeline_position` |
| `agent_completed` | `agent_role`, `duration_seconds`, `output_summary`, `token_count` |
| `approval_needed` | `agent_role`, `gate_number`, `output_preview`, `review_summary` |
| `deliverables_ready` | `download_urls` (zip, pptx, docx), `total_duration`, `total_cost` |
| `error` | `agent_role`, `error_type`, `error_message`, `stack_trace` |

## Delivery Guarantees

> [!decision] Fire-and-Forget Design
> Webhooks are **non-blocking and fire-and-forget**:
> - If the webhook call fails (network error, n8n down), the pipeline continues normally
> - No retries — the webhook is informational, not transactional
> - Timeout: 10 seconds per call
> - Logged but not persisted to database
>
> This is intentional. Webhooks exist for convenience (notifications, logging). The pipeline must never stall because an external service is down.

## Integration with n8n

The default webhook target is the [[n8n Integration|n8n instance]]. In n8n, each event type triggers a different workflow:

| Event | n8n Workflow |
|-------|-------------|
| `agent_started` | Log to activity feed |
| `agent_completed` | Update pipeline status dashboard |
| `approval_needed` | Send notification (Slack/email) |
| `deliverables_ready` | Notify Founder + log completion |
| `error` | Alert workflow (immediate notification) |

## Configuration

Webhook URL is set via environment variable:

```
# .env
WEBHOOK_URL=https://srv1867770.hstgr.cloud/webhook/pipeline-events
```

If `WEBHOOK_URL` is not set, webhooks are silently disabled. The [[Orchestrator]] calls `webhook.fire()` at each pipeline stage.

## Key Files

- `backend/app/services/webhook.py` — Event building + httpx delivery
- `backend/app/core/config.py` — `WEBHOOK_URL` configuration
- `backend/app/services/orchestrator.py` — Webhook call sites

---

Related: [[n8n Integration]], [[Orchestrator]], [[Pipeline Flow]], [[Tech Stack]], [[API Reference]]

#architecture #webhooks #integration
