# Agent Roster

## Overview

| Agent | Role | Approval Gate | Output Format |
|-------|------|--------------|---------------|
| CEO | Project Manager | No (auto-approved) | JSON |
| Business Analyst | Requirements | Yes | JSON |
| Researcher | Market Research | Yes | JSON |
| Architect | Technical Design | Yes | JSON |
| Engineer | Implementation | Yes | JSON -> .zip files |
| PPT | Presentation | No (auto-complete) | JSON -> .pptx file |

## Individual Agents

- [[CEO Agent]]
- [[Business Analyst Agent]]
- [[Researcher Agent]]
- [[Architect Agent]]
- [[Engineer Agent]]
- [[PPT Agent]]

## Cross-Review Assignments

Each agent's output is reviewed by the most relevant teammate before the Founder sees it:

| Agent Output | Reviewed By | Focus |
|-------------|-------------|-------|
| Business Analyst | CEO | Does analysis match the project brief? |
| Researcher | Business Analyst | Does research cover requirements? |
| Architect | Researcher | Are tech choices research-backed? |
| Engineer | Architect | Does code follow the architecture? |
| PPT | Engineer | Does the presentation match implementation? |

Reviews include a **quality score (1-10)**, alignment check, and hackathon readiness assessment. See [[Cross Review System]] for details.

## SIH-Optimized Prompts (v1.1)

All agent prompts were tuned for SIH hackathon context:

| Agent | SIH Optimization |
|-------|-----------------|
| CEO | 3 expansion examples for ultra-short inputs, Indian gov context (PM Kisan, DIKSHA) |
| BA | Indian personas mandatory (e.g., "Priya, Gram Panchayat secretary in MP"), DPDP Act 2023, 24h scope |
| Researcher | Bhashini API, IndiaAI, prior SIH winners, Indian sources (YourStory, Inc42) |
| Architect | Indian scale (1.4B people, 500M smartphones), Railway/Render hosting, UPI payments |
| Engineer | Indian locale (INR, IST, pincode), Indian sample data, 3-command setup |
| PPT | SIH judge criteria, Indian statistics and examples |

## Key Design Decisions

1. **Never consolidate roles** — each agent thinks differently about the same problem. A BA focuses on requirements, a Researcher on what exists, an Architect on how to build. Merging loses the focused perspective.

2. **JSON output** — every agent returns structured JSON, making it parseable, displayable, and storable. The Engineer's JSON includes complete file contents that get extracted to real files.

3. **Context inheritance** — each agent receives all previously approved outputs. The Architect sees the BA requirements AND the Research findings. The Engineer sees everything.

4. **Revision feedback** — when rejected, the agent gets the founder's feedback via shared memory and regenerates with that guidance.

Related: [[How It Works]], [[Orchestrator]], [[Cross Review System]]
