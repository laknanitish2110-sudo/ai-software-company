# Gap Analysis

A brutally honest audit of what's missing, what could break, and what would give us a competitive edge — done on Aug 9, 2026 with 9 days to SIH and 13 days to [[LaunchpadX]].

---

## Critical Gaps (Could Fail the Demo)

### Gap 1: No Retry / Error Handling

> [!status] Severity: CRITICAL
> | Detail | Value |
> |--------|-------|
> | **Risk** | One bad JSON response or timeout kills the entire pipeline |
> | **Where** | `backend/app/agents/engine.py` line 105-113 |
> | **Impact** | Demo dies mid-presentation if any agent fails |
> | **Current behavior** | `json.JSONDecodeError` saves raw text with `_parse_error` flag, but no retry |

**What's needed:**
- Retry logic (3 attempts with exponential backoff)
- JSON repair (strip markdown fences, fix trailing commas)
- Timeout handling (per-agent timeouts: 60s for CEO, 120s for BA/Researcher, 300s for Engineer)
- Graceful degradation (if cross-review fails, skip it and continue)

### Gap 2: Models Still on Nemotron 120B Free

> [!status] Severity: CRITICAL
> | Detail | Value |
> |--------|-------|
> | **Risk** | Free tier queuing = 5-30 min wait per agent |
> | **Where** | `backend/.env` — all 7 models set to `nvidia/nemotron-3-super-120b-a12b:free` |
> | **Impact** | Full pipeline takes 30+ minutes. Judges won't wait. |
> | **Planned fix** | Split strategy: Gemma 4 31B (free) for analysis, DeepSeek V3 (free) for Architect, Claude Sonnet 4 ($0.25) for Engineer |

See [[Model Strategy]] for the full cost breakdown.

### Gap 3: No Demo Fallback / Replay Mode

> [!status] Severity: CRITICAL
> | Detail | Value |
> |--------|-------|
> | **Risk** | If pipeline fails live, zero backup |
> | **Where** | No replay system exists |
> | **Impact** | Hackathon demo becomes "trust me it works" |

**What's needed:**
- Cache a complete successful run (all 6 agent outputs + deliverables)
- "Replay mode" that loads cached outputs instantly with simulated timing
- Fallback button in the [[Frontend Dashboard]] that loads the demo run
- Record a screen capture as ultimate backup

### Gap 4: No Streaming / Progress Feedback

> [!status] Severity: CRITICAL
> | Detail | Value |
> |--------|-------|
> | **Risk** | Engineer takes 400s with zero visual feedback |
> | **Where** | `engine.py` uses `client.chat.completions.create()` (blocking, not streaming) |
> | **Impact** | Judges think it's frozen/broken |

**What's needed:**
- Switch to `client.chat.completions.create(..., stream=True)`
- Stream tokens via WebSocket to frontend
- Show live token count, elapsed time, and "thinking" animation
- Per-agent progress: "Generating file 3 of 8..." for Engineer

---

## Important Gaps (Affects Quality)

### Gap 5: PPT Slides Are Basic

> [!decision] Severity: HIGH
> | Detail | Value |
> |--------|-------|
> | **Risk** | Plain white slides with text — looks amateur |
> | **Where** | `backend/app/services/pptx_generator.py` |
> | **Impact** | Presentation is a deliverable — its quality IS judged |

**What's needed:**
- Professional slide template (dark theme, accent colors, slide numbers)
- Title slide with project name, team, date
- Architecture diagram slide (auto-generated mermaid → image)
- Better text formatting (bullet hierarchy, font sizing)
- Cover slide, thank you slide, tech stack slide

### Gap 6: No Agent Visualization for Demo

> [!agent] Severity: HIGH
> | Detail | Value |
> |--------|-------|
> | **Risk** | LaunchpadX theme is "Agentic AI" — judges want to SEE agents |
> | **Where** | Frontend — Pipeline component shows a basic progress bar |
> | **Impact** | Missing the biggest opportunity to impress judges |

**What's needed:**
- **Live Agent Canvas**: Real-time visualization of agents as animated nodes
- Data flowing between agents as visible connections
- Token counter per agent (tokens in vs. tokens out)
- Cross-review arrows showing which agent reviewed which
- Agent status indicators: idle → thinking → generating → reviewing → done

This alone could win LaunchpadX. See [[Component Architecture]] for frontend structure.

### Gap 7: No Code Validation

> [!code] Severity: HIGH
> | Detail | Value |
> |--------|-------|
> | **Risk** | Engineer generates code that doesn't run |
> | **Where** | No validation between `engine.py` output and `file_generator.py` |
> | **Impact** | Judges download the ZIP, try to run it, it fails |

**What's needed:**
- Syntax check on generated files (at minimum, valid HTML/JS/Python)
- Dependency check (does package.json match imports?)
- Build test (if GitHub integration exists: push → CI → check build status)
- The Level 4 auto-fix loop handles this — see [[GitHub Integration]]

### Gap 8: Single API Key, No Failover

> [!status] Severity: MEDIUM
> | Detail | Value |
> |--------|-------|
> | **Risk** | OpenRouter rate limit or outage during demo |
> | **Where** | `backend/.env` — one API key, one provider |
> | **Impact** | Everything stops if the key is throttled |

**What's needed:**
- Backup OpenRouter API key (different account)
- OmniRoute as fallback router (already partially set up at `localhost:20128`)
- Direct provider keys as last resort (Anthropic for Claude, DeepSeek direct)
- Configurable failover chain in `config.py`

See [[OmniRoute Setup]] for the backup router.

---

## Competitive Edge Suggestions

### Gap 9: Live Agent Canvas

> [!pipeline] Severity: OPPORTUNITY
> A real-time visualization showing agents as animated nodes on a canvas:
> - Agents light up when active
> - Data packets flow along connection lines
> - Token counters tick up in real-time
> - Cross-review arrows pulse when reviews happen
> - Completion checkmarks animate in
>
> For a hackathon themed "Agentic AI," this is the money shot. Judges understand the architecture at a glance.

### Gap 10: Demo Script & Practice

> [!decision] Severity: OPPORTUNITY
> | Step | Content | Time |
> |------|---------|------|
> | 1 | "What if a team of 6 AI agents could build your entire project?" | 30s |
> | 2 | Paste a real SIH problem statement live | 15s |
> | 3 | Show CEO generating brief (streaming) | 30s |
> | 4 | Show BA/Researcher/Architect (fast forward or replay) | 60s |
> | 5 | Show Engineer generating code (streaming, files appearing) | 60s |
> | 6 | Show live deployed URL (Level 4) | 30s |
> | 7 | Show deliverables: working app + PPTX + DOCX + ZIP | 30s |
> | 8 | Show the agent canvas — "this is how they collaborate" | 30s |
> | 9 | Architecture slide + cost: "$0.26 per project" | 30s |
>
> Total: ~5 minutes. Practice this 10 times before the hackathon.

### Gap 11: Agent Introspection Panel

> [!agent] Severity: OPPORTUNITY
> Let judges click any agent node and see:
> - What context it received (input tokens)
> - What model it used and why
> - How long it took
> - Its peer review score and feedback
> - The raw output with syntax highlighting
>
> This shows deep understanding of agent architecture — not just "we used an API."

### Gap 12: Unique Output Guarantee

> [!decision] Severity: OPPORTUNITY
> "If 2 people give the same problem to ChatGPT, they get similar responses — what's the use?"
>
> Solutions:
> - **Temperature control**: Slightly randomize generation for variety
> - **Approval gate steering**: Different founder feedback → different direction → unique output
> - **Research personalization**: Tavily results vary by time, giving different context
> - **Show it in the demo**: Run the same problem twice with different approval feedback, show two different apps
>
> This directly addresses the differentiation question and proves the value of the approval gate architecture.

---

## Execution Plan

See [[Execution Plan]] for the day-by-day breakdown of what to tackle and when.

---

Related: [[Roadmap]], [[Model Strategy]], [[GitHub Integration]], [[Pipeline Flow]], [[Component Architecture]], [[LaunchpadX]], [[Orchestrator]]

#roadmap #gaps #critical #hackathon
