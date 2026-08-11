# Component Architecture

The frontend is a Next.js 16.3.0 application (React 19) using App Router with Tailwind CSS v4. This page maps every major component, its responsibility, and how they connect to the backend via API calls and WebSocket events.

## Component Tree

```mermaid
graph TD
    APP["App (layout.tsx)"] --> PROV["Providers"]
    PROV --> PAGE["page.tsx"]
    PAGE -->|"no project"| START["StartProject"]
    PAGE -->|"active project"| DASH["Dashboard"]
    DASH --> PIPE["PipelineView"]
    DASH --> CANVAS["AgentCanvas"]
    DASH --> OUTPUT["AgentOutput"]
    DASH --> CALL["CallEmployee"]
    DASH --> DELIV["DeliverableDownloads"]
    DASH --> SHARE["ShareButton"]
    DASH --> TOAST["Toast"]
    DASH -->|"loading"| SKEL["DashboardSkeleton"]
    OUTPUT --> REVIEW["PeerReview"]
    OUTPUT --> APPROVE["ApprovalPanel"]
    OUTPUT --> INTRO["AgentIntrospection"]
    PIPE --> STATUS["AgentStatusIndicator"]
    SKEL --> SKELCANVAS["SkeletonCanvas"]
    SKEL --> SKELCARD["SkeletonOutputCard"]
    SKEL --> SKELACT["SkeletonActivity"]

    style APP fill:#2563eb,stroke:#2563eb,color:#fff
    style DASH fill:#2563eb,stroke:#2563eb,color:#fff
    style SKEL fill:#94a3b8,stroke:#94a3b8,color:#fff
```

## Components

### Providers (`src/components/Providers.tsx`)

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/Providers.tsx` |
| **Purpose** | React context wrapper for toast notifications and shared state |
| **Wraps** | Entire app tree |

### StartProject (ProjectWizard)

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/StartProject.tsx` |
| **Purpose** | Problem statement input form — the entry point |
| **State** | Local state (controlled input) |
| **API call** | `POST /projects` to create project and start pipeline |
| **UX** | Text area + "Start Company" button. Minimal, focused. |

The Founder types a problem statement (from [[SIH Context|SIH's 498 problems]]) and clicks "Start Company." This creates a project in the [[Database Schema|database]] and triggers the [[Orchestrator]].

### Dashboard

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/Dashboard.tsx` |
| **Purpose** | Main view after project starts — shows all pipeline activity |
| **State** | WebSocket-driven (real-time updates) |
| **Loading** | Shows `DashboardSkeleton` with shimmer animations while data loads |
| **Children** | PipelineView, AgentCanvas, AgentOutput (x6), CallEmployee, DeliverableDownloads, ShareButton, Toast |
| **Layout** | Left: pipeline progress. Center: agent outputs. Right: actions. |

### PipelineView

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/Pipeline.tsx` |
| **Purpose** | Visual representation of the 6-agent pipeline |
| **Shows** | Agent status indicators, gate states, progress flow |
| **Updates** | Via WebSocket events from [[Orchestrator]] |

Agent states rendered:

| State | Visual | Meaning |
|-------|--------|---------|
| `pending` | Gray circle | Not started yet |
| `running` | Pulsing blue | Agent is processing |
| `review` | Yellow circle | Waiting for approval ([[Approval Gate Design|Gate]]) |
| `approved` | Green checkmark | Founder approved |
| `rejected` | Red circle | Founder rejected, agent revising |
| `completed` | Green checkmark | Done (auto-approved agents) |
| `error` | Red X | Agent failed |

### AgentCanvas

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/AgentCanvas.tsx` |
| **Purpose** | Visual node layout for pipeline agents |
| **Shows** | 6 agent nodes with connecting lines and status colors |

### AgentOutput

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/AgentOutput.tsx` |
| **Purpose** | Displays one agent's output as a formatted card |
| **Children** | PeerReview (with ScoreBadge), ApprovalPanel, AgentIntrospection |
| **Features** | Expandable sections, formatted JSON, code blocks |
| **Updates** | WebSocket event when agent completes |

### PeerReview

| Property | Details |
|----------|---------|
| **File** | Part of `AgentOutput.tsx` |
| **Purpose** | Displays [[Cross Review System|cross-review]] commentary |
| **Shows** | Quality score badge (color-coded 1-10), reviewer's team note, alignment check, hackathon readiness, strengths, concerns, suggestions |
| **Styling** | Quoted block with reviewer attribution + ScoreBadge component |

### ScoreBadge

| Property | Details |
|----------|---------|
| **File** | Part of `AgentOutput.tsx` |
| **Purpose** | Color-coded quality score indicator |
| **Colors** | Green (8+), Blue (6-7), Yellow (4-5), Red (1-3) |

### AgentIntrospection

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/AgentIntrospection.tsx` |
| **Purpose** | Expandable panel showing agent's internal reasoning |
| **Shows** | Token usage, model used, processing time |
| **UX** | Collapsed by default, click to expand |

### ApprovalPanel

| Property | Details |
|----------|---------|
| **File** | Part of `AgentOutput.tsx` |
| **Purpose** | Approve/Reject buttons + feedback text area |
| **API calls** | `POST /projects/{id}/approve`, `POST /projects/{id}/reject` |
| **Visibility** | Only shown when agent is in "review" state |

### CallEmployee

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/CallEmployee.tsx` |
| **Purpose** | Direct chat with any agent |
| **API call** | `POST /projects/{id}/call-employee` |
| **Features** | Select agent dropdown, chat interface, context-aware responses |
| **Special** | [[Engineer Agent]] enters "pair programming mode" — returns updated files |

### DeliverableDownloads

| Property | Details |
|----------|---------|
| **File** | Part of `Dashboard.tsx` |
| **Purpose** | Download buttons for generated files |
| **Files** | `.zip` (code), `.pptx` (slides), `.docx` (report) |
| **Visibility** | Only shown when pipeline is complete |
| **Backend** | [[File Generator]] produces the files |

### ShareButton

| Property | Details |
|----------|---------|
| **File** | Part of `Dashboard.tsx` |
| **Purpose** | Generate a shareable link to the project output |
| **API call** | `POST /projects/{id}/share` |

### Toast

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/Toast.tsx` |
| **Purpose** | Toast notification system with auto-dismiss |
| **Types** | Success (green), Error (red), Warning (yellow), Info (blue) |
| **UX** | Stacks multiple toasts vertically, auto-dismiss after timeout |

### Skeleton Components

| Property | Details |
|----------|---------|
| **File** | `frontend/src/components/Skeleton.tsx` |
| **Purpose** | Full-page loading placeholder system |
| **Sub-components** | `DashboardSkeleton`, `SkeletonCanvas` (6 circles), `SkeletonOutputCard` (avatar + text), `SkeletonActivity` (sidebar feed), `SkeletonLine` |
| **Animations** | `@keyframes shimmer` (linear gradient slide), `@keyframes pulseSubtle` (opacity pulse) |

## Data Flow

```
User action -> API call -> Backend processes -> WebSocket event -> State update -> UI re-render
```

All real-time updates come through a single WebSocket connection per project. The [[API Reference]] documents all endpoints used by these components.

## Styling

Components use a mix of Tailwind CSS v4 utility classes and CSS Variables for theming. See [[Theme & Design]] for the complete design system. Skeleton animations are defined in `globals.css`.

---

Related: [[Frontend Dashboard]], [[Theme & Design]], [[API Reference]], [[Orchestrator]], [[Approval Gate Design]], [[Cross Review System]]

#frontend #components #architecture
