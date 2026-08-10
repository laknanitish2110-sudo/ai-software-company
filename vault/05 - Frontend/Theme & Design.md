# Theme & Design

The frontend uses a custom **light theme** built entirely with CSS Variables. No Tailwind CSS, no component library — full control over every pixel. This page documents the design system, color palette, and visual language.

## Design Philosophy

> [!decision] Custom CSS Over Frameworks
> Why not Tailwind or Material UI?
> - **Full control**: Every spacing, color, and animation is intentional
> - **No dependency**: CSS variables are native, zero bundle impact
> - **Easy theming**: Swap variable values for dark mode in [[V2 Vision|V2]]
> - **Performance**: No unused CSS to purge, no runtime overhead
> - **Hackathon speed**: Once the variables are set, styling is fast

## Color Palette

### Primary Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-primary` | `#2563eb` | Buttons, links, active states |
| `--color-primary-hover` | `#1d4ed8` | Button hover states |
| `--color-primary-light` | `#dbeafe` | Selected backgrounds, badges |

### Surface Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg` | `#ffffff` | Page background |
| `--color-surface` | `#f8fafc` | Card backgrounds |
| `--color-surface-hover` | `#f1f5f9` | Card hover states |
| `--color-border` | `#e2e8f0` | Subtle borders, dividers |

### Text Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-text` | `#0f172a` | Primary text |
| `--color-text-secondary` | `#64748b` | Secondary text, labels |
| `--color-text-muted` | `#94a3b8` | Placeholder text, hints |

### Status Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-success` | `#22c55e` | Approved, completed |
| `--color-warning` | `#f59e0b` | Waiting, review needed |
| `--color-error` | `#ef4444` | Rejected, error |
| `--color-info` | `#3b82f6` | Running, processing |

## Agent Colors

Each agent in the pipeline has a unique accent color for identification:

| Agent | Color | Hex |
|-------|-------|-----|
| [[CEO Agent]] | Gold | `#f5a623` |
| [[Business Analyst Agent]] | Blue | `#4a90d9` |
| [[Researcher Agent]] | Green | `#50b83c` |
| [[Architect Agent]] | Purple | `#9b59b6` |
| [[Engineer Agent]] | Red | `#ed5f74` |
| [[PPT Agent]] | Orange | `#e67e22` |

These colors appear in the [[Component Architecture|PipelineView]] as status indicators and in the [[Frontend Dashboard|Dashboard]] as agent card accents.

## Layout System

### Dashboard Layout

```
┌──────────────────────────────────────────────┐
│  Header (project name, status, actions)       │
├──────────┬────────────────────┬──────────────┤
│          │                    │              │
│ Pipeline │   Agent Outputs    │   Actions    │
│ Progress │   (scrollable)     │   Panel      │
│          │                    │              │
│  ┌───┐   │  ┌──────────────┐  │  Call        │
│  │CEO│   │  │ Agent Card   │  │  Employee    │
│  ├───┤   │  │  + Review    │  │              │
│  │ BA│   │  │  + Approve   │  │  Downloads   │
│  ├───┤   │  └──────────────┘  │  (.zip)      │
│  │RES│   │                    │  (.pptx)     │
│  ├───┤   │  ┌──────────────┐  │  (.docx)     │
│  │ARC│   │  │ Agent Card   │  │              │
│  ├───┤   │  └──────────────┘  │  Share       │
│  │ENG│   │                    │              │
│  ├───┤   │                    │              │
│  │PPT│   │                    │              │
│  └───┘   │                    │              │
└──────────┴────────────────────┴──────────────┘
```

### Spacing System

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` | Inline spacing, icon gaps |
| `--space-sm` | `8px` | Tight component spacing |
| `--space-md` | `16px` | Standard padding |
| `--space-lg` | `24px` | Section spacing |
| `--space-xl` | `32px` | Major section gaps |

### Typography

| Element | Size | Weight |
|---------|------|--------|
| Page title | 24px | 700 |
| Section heading | 18px | 600 |
| Body text | 14px | 400 |
| Small text / labels | 12px | 500 |
| Code / monospace | 13px | 400 |

Font stack: `Inter, -apple-system, BlinkMacSystemFont, sans-serif`

## Pipeline Visualization

The pipeline view uses connected nodes with agent-specific colors:

> [!status] Agent Status Indicators
> | State | Visual Treatment |
> |-------|-----------------|
> | Pending | Gray fill, dashed border |
> | Running | Agent color fill, pulse animation (CSS keyframes) |
> | Review | Yellow border, solid fill |
> | Approved | Green fill, checkmark icon |
> | Rejected | Red border, exclamation icon |
> | Error | Red fill, X icon |

## Animations

| Animation | Duration | Easing | Usage |
|-----------|----------|--------|-------|
| Pulse | 2s | ease-in-out | Running agent indicator |
| Fade in | 200ms | ease-out | New content appearing |
| Slide up | 300ms | ease-out | Agent output cards entering |
| Collapse | 200ms | ease-in | Approved output collapsing |

## Dark Mode (V2)

> [!pipeline] Planned for V2
> Dark mode is not in V1 but the architecture supports it. All colors use CSS variables — swapping to dark mode means changing ~20 variable values. No component changes needed.
>
> See [[V2 Vision]] for post-hackathon plans.

---

Related: [[Component Architecture]], [[Frontend Dashboard]], [[Agent Roster]], [[Tech Stack]], [[V2 Vision]]

#frontend #design #theme
