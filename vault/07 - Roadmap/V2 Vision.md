# V2 Vision

Post-hackathon roadmap for turning the AI Software Company from a hackathon project into a real product. V1 proves the concept; V1.5 adds [[GitHub Integration|auto-deploy]]; V2 makes it production-ready.

## The Big Picture

> [!pipeline] From Hackathon Tool to Product
> V1 generates code as a ZIP. V1.5 deploys it live. V2 lets multiple users build simultaneously, customize their agents, and build a portfolio of generated projects.

```mermaid
graph LR
    V1["V1: Pipeline Works"] --> V15["V1.5: Auto-Deploy"]
    V15 --> V2["V2: Product"]
    V2 --> V3["V3: Platform"]
    style V1 fill:#0bbf8c,stroke:#0bbf8c,color:#0f0f14
    style V15 fill:#635bff,stroke:#635bff,color:#fff
    style V2 fill:#a855f7,stroke:#a855f7,color:#fff
    style V3 fill:#ed5f74,stroke:#ed5f74,color:#fff
```

## V2 Features

### Multi-User Support

> [!agent] User Accounts & Teams
> - Authentication (OAuth with Google/GitHub)
> - Each user gets their own project history
> - Team workspaces for collaborative hackathons
> - Role-based access: admin, builder, viewer

### Custom Agent Prompts

> [!decision] User-Tunable Agents
> Let users customize agent behavior without touching code:
> - Custom system prompts per agent
> - Domain-specific templates (healthcare, fintech, edtech)
> - Save and share prompt configurations
> - A/B test different prompt strategies

### Project Portfolio

| Feature | Description |
|---------|-------------|
| **Gallery** | Browse all generated projects with live previews |
| **Search** | Find projects by tech stack, domain, or problem type |
| **Fork** | Take any project as a starting point for a new one |
| **Ratings** | Community ratings on generated project quality |
| **Export** | One-click export to GitHub, Vercel, or ZIP |

### Analytics Dashboard

> [!status] Pipeline Intelligence
> - Track agent performance over time (speed, quality scores)
> - Cost analytics per user and per project
> - Model comparison: which models produce better code for which domains
> - Success rate tracking: how many generated projects actually build and deploy

### Agent Marketplace

> [!pipeline] Custom Agent Templates
> Power users create specialized agent configurations:
> - "Mobile-First Architect" — always picks React Native + Expo
> - "Government Portal BA" — trained on Indian govt UX guidelines
> - "Security-First Engineer" — adds auth, CORS, rate limiting by default
> - Community-contributed templates with ratings

## Technical Requirements

| Component | Current (V1) | V2 Target |
|-----------|-------------|-----------|
| **Database** | SQLite | PostgreSQL |
| **Auth** | None | OAuth 2.0 (Google, GitHub) |
| **Storage** | Local filesystem | S3/R2 (Cloudflare) |
| **Queue** | Synchronous | Redis + Celery |
| **Cache** | None | Redis |
| **CDN** | None | Cloudflare |
| **Monitoring** | n8n webhooks | Grafana + Prometheus |

## Revenue Model

> [!decision] Pricing Strategy (Tentative)
> | Tier | Price | Runs/Month | Features |
> |------|-------|-----------|----------|
> | **Free** | $0 | 3 | Basic pipeline, ZIP output only |
> | **Pro** | $9/mo | 30 | Auto-deploy, custom prompts, portfolio |
> | **Team** | $29/mo | 100 | Multi-user, shared workspace, analytics |
> | **Enterprise** | Custom | Unlimited | Self-hosted, custom agents, SLA |
>
> At ~$0.26/run cost, Pro tier has 67% margin. Free tier is a loss leader.

## Timeline

| Phase | Target | Milestone |
|-------|--------|-----------|
| **V1** | Aug 2026 | Pipeline works, hackathon-ready |
| **V1.5** | Sep 2026 | [[GitHub Integration]], live deploy |
| **V2 Alpha** | Nov 2026 | Multi-user, PostgreSQL migration |
| **V2 Beta** | Jan 2027 | Agent marketplace, analytics |
| **V2 Launch** | Mar 2027 | Public launch |

## What Makes V2 Different From ChatGPT

> [!decision] The Differentiation Question
> "If 2 people give the same problem to ChatGPT, they get similar responses — what's the use?"
>
> V2 answers this with:
> 1. **6 specialized agents** — not one generalist. Each agent thinks differently about the same problem.
> 2. **Real deployed apps** — not code in a chat window. Click a link, see it working.
> 3. **Customizable agents** — your prompts, your domain expertise baked in.
> 4. **Approval gates** — you steer the output at every stage, so two users get different results even from the same input.
> 5. **Cross-review** — agents review each other's work. ChatGPT reviews nothing.
>
> See [[Six Agent Architecture]] for why this matters.

---

Related: [[Roadmap]], [[GitHub Integration]], [[Six Agent Architecture]], [[Model Strategy]], [[Budget & Costs]], [[Project Vision]]

#roadmap #v2 #product #vision
