# API Reference

**Base URL:** `http://localhost:8000`

## REST Endpoints

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/projects` | Create new project, starts pipeline |
| `GET` | `/api/projects` | List all projects |
| `GET` | `/api/projects/{id}` | Get full project state (project + outputs + memory) |
| `GET` | `/api/projects/{id}/outputs` | Get all agent outputs for a project |
| `GET` | `/api/projects/{id}/memory` | Get shared memory entries |

### Approval Gates

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/projects/{id}/approve/{output_id}` | Approve or reject an agent's output |

**Request body:**
```json
{
  "approved": true,
  "feedback": "optional feedback if rejecting"
}
```

### Call Employee (Direct Chat)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/projects/{id}/call` | Send a message to any agent |
| `GET` | `/api/projects/{id}/conversation/{role}` | Get chat history with an agent |

**Request body (call):**
```json
{
  "role": "engineer",
  "message": "Can you add dark mode to the React app?"
}
```

### Downloads

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/projects/{id}/download/code` | Download generated project as `.zip` |
| `GET` | `/api/projects/{id}/download/pptx` | Download presentation as `.pptx` |
| `GET` | `/api/projects/{id}/download/docx` | Download documentation as `.docx` |
| `GET` | `/api/projects/{id}/files` | List all generated files |

### Integrations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/integrations/status` | Get status of all integrations (n8n, GitHub, etc.) |

### Sharing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/projects/{id}/share` | Share project deliverables (Drive, Sheets, Email) |

**Request body (share):**
```json
{
  "target": "google_drive",
  "file_types": ["zip", "pptx", "docx"]
}
```

> [!status] Share Targets
> | Target | Description |
> |--------|-------------|
> | `google_drive` | Upload deliverables to Google Drive folder |
> | `google_sheets` | Log project data to a Google Sheet |
> | `email` | Send deliverables via email |
> | `share_all` | Send to all configured targets |

### WebSocket

| Protocol | Endpoint | Description |
|----------|----------|-------------|
| `WS` | `/api/ws/{project_id}` | Real-time pipeline updates |

**Message format (received):**
```json
{
  "type": "agent_started",
  "data": {
    "role": "business_analyst",
    "message": "Business Analyst started working"
  }
}
```

**Event types:** `agent_started`, `agent_completed`, `cross_review_completed`, `approval_needed`, `approval_accepted`, `revision_requested`, `files_generated`, `pptx_generated`, `docx_generated`, `project_completed`, `error`

## Endpoint Summary

> [!pipeline] 12 Endpoints Total
> | Category | Count | Endpoints |
> |----------|-------|-----------|
> | Projects | 5 | CRUD + outputs + memory |
> | Approval | 1 | Approve/reject |
> | Chat | 2 | Call + conversation history |
> | Downloads | 4 | Code, PPTX, DOCX, file list |
> | Integrations | 1 | Status check |
> | Sharing | 1 | Share deliverables |
> | WebSocket | 1 | Real-time updates |

## Key Files

- **Routes:** `backend/app/api/routes.py`
- **Schemas:** `backend/app/models/schemas.py`
- **Main app:** `backend/app/main.py`
- **Webhook service:** `backend/app/services/webhook.py`

---

Related: [[Orchestrator]], [[Tech Stack]], [[n8n Integration]], [[Frontend Dashboard]]

#api #endpoints
