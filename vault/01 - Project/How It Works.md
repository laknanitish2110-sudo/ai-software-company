# How It Works

## The Pipeline

```
Founder → CEO → BA → [Approve] → Researcher → [Approve] → Architect → [Approve] → Engineer → [Approve] → PPT → Done
```

### Step-by-step:

| Step | Agent | What Happens | Founder Action |
|------|-------|-------------|----------------|
| 1 | **You** | Paste problem statement, click "Start Company" | Start |
| 2 | **CEO** | Creates project brief, assigns work | Automatic |
| 3 | **Business Analyst** | Produces requirements, user stories, scope | **Approve or Reject** |
| 4 | **Researcher** | Searches web, compares competitors, finds APIs | **Approve or Reject** |
| 5 | **Architect** | Designs tech stack, DB, APIs with trade-offs | **Approve or Reject** |
| 6 | **Engineer** | Writes complete runnable code | **Approve or Reject** |
| 7 | **PPT Agent** | Creates slides, README, pitch | Automatic (final) |

### Key Points:
- You only approve **4 times** — everything else is automatic
- If you reject, you provide feedback and the agent revises
- Each agent can see all previous approved outputs
- The Engineer only starts after Architecture is approved
- When complete, you download a `.zip` of code and a `.pptx` presentation

## "Call Employee" Feature

At any point, you can open a direct chat with any agent:

- Click "Call Employee" → pick an agent
- Ask them anything about the project
- They answer from their expertise + full project context
- The Engineer enters "pair programming mode" — gives you complete updated files

## Shared Memory

All agents share a project memory:
- Problem statement
- CEO brief
- Each agent's summary
- Revision feedback
- All approved outputs

No agent works in isolation. Everyone knows what the others decided.

Related: [[Agent Roster]], [[Orchestrator]], [[Project Vision]]
