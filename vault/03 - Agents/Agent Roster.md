# Agent Roster

## Overview

| Agent | Role | Approval Gate | Output Format |
|-------|------|--------------|---------------|
| CEO | Project Manager | No (auto-approved) | JSON |
| Business Analyst | Requirements | Yes | JSON |
| Researcher | Market Research | Yes | JSON |
| Architect | Technical Design | Yes | JSON |
| Engineer | Implementation | Yes | JSON → .zip files |
| PPT | Presentation | No (auto-complete) | JSON → .pptx file |

## Individual Agents

- [[CEO Agent]]
- [[Business Analyst Agent]]
- [[Researcher Agent]]
- [[Architect Agent]]
- [[Engineer Agent]]
- [[PPT Agent]]

## Key Design Decisions

1. **Never consolidate roles** — each agent thinks differently about the same problem. A BA focuses on requirements, a Researcher on what exists, an Architect on how to build. Merging loses the focused perspective.

2. **JSON output** — every agent returns structured JSON, making it parseable, displayable, and storable. The Engineer's JSON includes complete file contents that get extracted to real files.

3. **Context inheritance** — each agent receives all previously approved outputs. The Architect sees the BA requirements AND the Research findings. The Engineer sees everything.

4. **Revision feedback** — when rejected, the agent gets the founder's feedback via shared memory and regenerates with that guidance.

Related: [[How It Works]], [[Orchestrator]]
