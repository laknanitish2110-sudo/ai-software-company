# Frontend Dashboard

**Stack:** Next.js 16 (App Router) + TypeScript + CSS Variables (Light Theme)
**Port:** `http://localhost:3000`

## Page Flow

```
Landing Page (StartProject)
  |
  |  User enters problem statement -> clicks "Start Company"
  |
  v
Dashboard
  ├── Header (project name + status badge + download buttons + share buttons)
  ├── Pipeline visualization (horizontal agent progress)
  ├── Tab: Employee Outputs (agent output cards)
  ├── Tab: Call Employee (direct chat with any agent)
  ├── Activity Feed (real-time WebSocket events)
  └── n8n Connection Status Badge
```

## Theme

> [!decision] Light Theme with CSS Variables
> The dashboard uses a **custom light theme** built entirely with CSS variables — no Tailwind CSS. This was a deliberate design choice:
> - Full control over every color and spacing value
> - Easy to add dark mode later (swap variable values)
> - Accent color: `#635bff` (electric purple)
> - Clean, professional look suitable for hackathon demos
>
> The theme was changed from dark to light during development for better readability during live demos and presentations.

### CSS Variable Categories

| Category | Examples |
|----------|---------|
| **Colors** | `--color-primary`, `--color-surface`, `--color-text` |
| **Spacing** | `--space-sm`, `--space-md`, `--space-lg` |
| **Borders** | `--radius-sm`, `--radius-md`, `--border-color` |
| **Shadows** | `--shadow-sm`, `--shadow-md`, `--shadow-lg` |
| **Typography** | `--font-body`, `--font-mono`, `--font-size-base` |

## Components

### StartProject (`src/components/StartProject.tsx`)
- Textarea for problem statement input
- "Start Company" button
- 6 agent preview cards showing what each agent will do
- Light theme with purple accent

### Dashboard (`src/components/Dashboard.tsx`)
- Main container after project creation
- Header shows project name extracted from CEO output
- Download buttons appear when status = `completed`:
  - Code `.zip` — complete runnable project
  - Presentation `.pptx` — pitch deck slides
  - Documentation `.docx` — project documentation
- **Share buttons** for external distribution:
  - Google Drive — upload all deliverables
  - Google Sheets — log project data
  - Email — send deliverables to recipients
  - Share All — send to all configured targets
- **n8n connection status badge** — shows whether webhook events are being delivered
- Two-tab layout:
  - **Employee Outputs** — all agent outputs in a scrollable column
  - **Call Employee** — direct chat interface
- Right sidebar: activity feed with color-coded events
- Connects WebSocket on mount, refreshes state on each event

### Pipeline (`src/components/Pipeline.tsx`)
- Horizontal row of 6 agent badges connected by arrows
- State per agent:
  - **Done** (green) — output approved
  - **Active** (purple, pulsing) — agent currently working
  - **Review** (amber) — waiting for founder approval
  - **Waiting** (gray) — not started yet

### AgentOutput (`src/components/AgentOutput.tsx`)
- Expandable card for each agent's output
- Shows: role icon, label, status badge (pending/approved/rejected)
- Renders nested JSON content recursively
- Approve and Reject buttons when `showActions=true`
- Reject opens feedback textarea

### CallEmployee (`src/components/CallEmployee.tsx`)
- Phase 1: Agent selector grid (6 agent cards)
- Phase 2: Chat interface with selected agent
  - Message history (user + agent messages)
  - Text input + send button
  - "Thinking..." animation while waiting
  - Engineer enters iteration mode for complete file updates

## Share Buttons

> [!pipeline] External Sharing
> | Button | Action | n8n Event |
> |--------|--------|-----------|
> | Google Drive | Upload ZIP + PPTX + DOCX to Drive folder | `share` (target: google_drive) |
> | Google Sheets | Log project data and agent outputs | `share` (target: google_sheets) |
> | Email | Send deliverables to email recipients | `share` (target: email) |
> | Share All | Trigger all share targets at once | `share` (target: share_all) |
>
> Share buttons call `POST /api/projects/{id}/share` which triggers a webhook to [[n8n Integration]].

## n8n Connection Badge

> [!status] Integration Status
> The dashboard header shows a small badge indicating whether the n8n webhook endpoint is reachable:
> - **Connected** (green dot) — webhooks are being delivered
> - **Disconnected** (red dot) — n8n instance unreachable
>
> Status is checked via `GET /api/integrations/status`.

## API Client (`src/lib/api.ts`)
- Typed interfaces matching backend schemas
- Functions: `createProject()`, `getProjects()`, `getProjectState()`, `approveOutput()`, `callEmployee()`, `getConversation()`, `downloadCode()`, `downloadPptx()`, `downloadDocx()`, `shareProject()`, `getIntegrationStatus()`, `connectWebSocket()`

## Agent Config (`src/lib/constants.ts`)
- `AGENT_CONFIG` — label, icon, color, description per agent role
- `PIPELINE_ORDER` — ordered array of agent roles
- `STATUS_LABELS` — human-readable status strings

---

Related: [[API Reference]], [[How It Works]], [[n8n Integration]], [[Tech Stack]]

#frontend #dashboard #ui
