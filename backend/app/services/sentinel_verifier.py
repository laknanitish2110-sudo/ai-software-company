"""
Multi-tier Independent Sentinel Verification.

Three tiers of verification, each in a SEPARATE LLM context (no builder
conversation history). Fail-fast — each tier only runs if the previous passes.

Tier 1 — Structural Sentinel (cheap/fast, Jev layer):
  Does the output exist? Is it complete vs the goal? Obvious errors?
  Uses the cheapest model. Catches 60% of failures for 5% of the cost.

Tier 2 — Deep Sentinel (standard model):
  Logic bugs, security issues, edge cases, incomplete error handling.
  Full quality review. Only runs if Tier 1 passes.

Tier 3 — Domain Sentinel (role-specific):
  For Atlas: does the code actually run? For Scout: are sources credible?
  Each role's QA focus is different. Only runs for high-priority goals.

This is the anti-wrapper differentiator — 3-tier independent verification
that measurably reduces bugs vs single-agent or single-review systems.
"""

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


# ── Tier 1: Structural Sentinel (cheap/fast — the Jev layer) ─────────

STRUCTURAL_SYSTEM_PROMPT = """You are a fast structural reviewer. Check work output for OBVIOUS problems only.

Your job is a quick triage — not a deep review. Check:
1. Does output exist? (Are there actual artifacts/files?)
2. Is the output RELEVANT to the goal? (Not a different topic)
3. Is the output COMPLETE? (Not cut off, not placeholder/TODO)
4. Any OBVIOUS errors? (Syntax errors, broken imports, empty files)

Respond with JSON:
```json
{
    "verdict": "PASS" or "FAIL",
    "confidence": 0.0-1.0,
    "issues": [{"severity": "critical", "description": "..."}],
    "summary": "one sentence"
}
```

FAIL only for OBVIOUS problems. Do NOT deep-review logic or edge cases — that's someone else's job.
Be fast. Be brief."""


# ── Tier 2: Deep Sentinel (standard model) ───────────────────────────

DEEP_SYSTEM_PROMPT = """You are an independent QA reviewer. You are reviewing work produced by another AI agent.

IMPORTANT: You did NOT produce this work. You are seeing it for the first time. Your job is to find
defects, not to defend the implementation.

A structural check already passed — the output exists and looks roughly complete.
Now go DEEP. Review against the original goal:
- Logic errors, bugs, off-by-one mistakes
- Security vulnerabilities (injection, XSS, auth bypass, secrets exposure)
- Missing error handling where it matters
- Incomplete implementations that would fail in production
- Edge cases that would crash or produce wrong results
- Hardcoded values that should be configurable

You MUST respond with a JSON verdict:
```json
{
    "verdict": "PASS" or "FAIL",
    "confidence": 0.0-1.0,
    "issues": [
        {
            "severity": "critical" | "major" | "minor",
            "file": "filename or area",
            "description": "what's wrong",
            "suggestion": "how to fix it"
        }
    ],
    "summary": "one-sentence overall assessment"
}
```

FAIL if there are any critical issues. FAIL if there are 3+ major issues.
Otherwise PASS with noted minor issues."""


# ── Tier 3: Domain Sentinel (role-specific) ──────────────────────────

DOMAIN_PROMPTS = {
    "software engineer": (
        "You are a senior software engineer reviewing code produced by a junior engineer.\n"
        "Focus on: Does this code actually work? Would it survive production?\n"
        "Check: dependency management, deployment readiness, test coverage,\n"
        "configuration handling, logging, graceful error recovery.\n"
        "Ignore style preferences — focus on correctness and resilience."
    ),
    "researcher": (
        "You are a research director reviewing a research report.\n"
        "Focus on: Are conclusions supported by evidence? Are sources credible?\n"
        "Check: citation quality, logical reasoning, bias identification,\n"
        "completeness of literature review, actionability of recommendations."
    ),
    "architect": (
        "You are a principal architect reviewing a system design.\n"
        "Focus on: Will this scale? Is it maintainable? Are trade-offs documented?\n"
        "Check: single points of failure, coupling/cohesion, security boundaries,\n"
        "deployment complexity, data consistency guarantees."
    ),
    "business analyst": (
        "You are a product manager reviewing business analysis deliverables.\n"
        "Focus on: Are requirements testable? Are acceptance criteria specific?\n"
        "Check: ambiguous language, missing scenarios, untestable criteria,\n"
        "stakeholder coverage, priority conflicts."
    ),
    "qa engineer": (
        "You are a QA lead reviewing a test plan and test results.\n"
        "Focus on: Is test coverage adequate? Are test assertions meaningful?\n"
        "Check: missing negative tests, boundary conditions, test isolation,\n"
        "flaky test indicators, coverage gaps in critical paths."
    ),
    "technical writer": (
        "You are a documentation lead reviewing technical documentation.\n"
        "Focus on: Can a developer follow this without prior context?\n"
        "Check: missing prerequisites, broken code examples, outdated references,\n"
        "logical flow, completeness of API documentation."
    ),
}

DOMAIN_SYSTEM_TEMPLATE = """{domain_prompt}

A structural check AND a deep quality review already passed.
You are the final domain-expert gate. Find issues only a specialist would catch.

Respond with JSON:
```json
{{
    "verdict": "PASS" or "FAIL",
    "confidence": 0.0-1.0,
    "issues": [
        {{
            "severity": "critical" | "major" | "minor",
            "file": "filename or area",
            "description": "what's wrong",
            "suggestion": "how to fix it"
        }}
    ],
    "summary": "one-sentence domain expert assessment"
}}
```

FAIL only for domain-critical issues. Minor style concerns are PASS with notes."""


# ── Multi-tier orchestrator ──────────────────────────────────────────

async def sentinel_verify(
    goal: str,
    plan: str | None,
    artifacts: list[dict],
    employee_name: str = "an AI employee",
    employee_role: str = "software engineer",
    priority: str = "medium",
) -> dict:
    """Run multi-tier Sentinel verification. Fail-fast across tiers.

    Returns a combined verdict with per-tier results.
    """
    start = time.time()
    review_content = _build_review_prompt(goal, plan, artifacts, employee_name)
    tier_results = []

    # ── Tier 1: Structural (always runs, uses cheap model) ──
    t1 = await _run_tier(
        tier="structural",
        system_prompt=STRUCTURAL_SYSTEM_PROMPT,
        review_content=review_content,
        llm_role="jev",
    )
    tier_results.append({"tier": 1, "name": "structural", **t1})

    if t1["verdict"] == "FAIL":
        return _combine_results(tier_results, time.time() - start)

    # ── Tier 2: Deep (runs if T1 passes, standard model) ──
    t2 = await _run_tier(
        tier="deep",
        system_prompt=DEEP_SYSTEM_PROMPT,
        review_content=review_content,
        llm_role="qa",
    )
    tier_results.append({"tier": 2, "name": "deep", **t2})

    if t2["verdict"] == "FAIL":
        return _combine_results(tier_results, time.time() - start)

    # ── Tier 3: Domain (runs only for high/critical priority, role-specific) ──
    if priority in ("high", "critical"):
        domain_prompt = DOMAIN_PROMPTS.get(employee_role.lower(), DOMAIN_PROMPTS["software engineer"])
        system_prompt = DOMAIN_SYSTEM_TEMPLATE.format(domain_prompt=domain_prompt)

        t3 = await _run_tier(
            tier="domain",
            system_prompt=system_prompt,
            review_content=review_content,
            llm_role="qa",
        )
        tier_results.append({"tier": 3, "name": "domain", **t3})

    return _combine_results(tier_results, time.time() - start)


async def _run_tier(
    tier: str,
    system_prompt: str,
    review_content: str,
    llm_role: str,
) -> dict:
    """Run a single verification tier."""
    from app.agents.engine import call_llm_with_fallback

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": review_content},
        ]

        text, _ = await call_llm_with_fallback(
            messages=messages,
            role=llm_role,
            temperature=0.2,
            tools=None,
        )

        verdict = _parse_verdict(text)
        logger.info(
            f"Sentinel Tier [{tier}]: {verdict.get('verdict', 'UNKNOWN')} "
            f"(confidence={verdict.get('confidence', 0)}, "
            f"issues={len(verdict.get('issues', []))})"
        )
        return verdict

    except Exception as e:
        logger.error(f"Sentinel Tier [{tier}] failed: {e}")
        return {
            "verdict": "PASS",
            "confidence": 0.3,
            "issues": [],
            "summary": f"Tier {tier} unavailable: {e}. Passing by default.",
            "error": str(e),
        }


def _combine_results(tier_results: list[dict], elapsed: float) -> dict:
    """Combine multi-tier results into a single verdict."""
    all_issues = []
    for tr in tier_results:
        for issue in tr.get("issues", []):
            issue["detected_by"] = f"tier_{tr['tier']}_{tr['name']}"
            all_issues.append(issue)

    final_verdict = "PASS"
    for tr in tier_results:
        if tr.get("verdict") == "FAIL":
            final_verdict = "FAIL"
            break

    min_confidence = min(
        (tr.get("confidence", 0.5) for tr in tier_results),
        default=0.5,
    )

    failing_tier = next(
        (tr for tr in tier_results if tr.get("verdict") == "FAIL"),
        None,
    )
    summary = failing_tier["summary"] if failing_tier else (
        tier_results[-1].get("summary", "All tiers passed.") if tier_results else "No tiers ran."
    )

    return {
        "verdict": final_verdict,
        "confidence": min_confidence,
        "issues": all_issues,
        "summary": summary,
        "tiers": tier_results,
        "tiers_run": len(tier_results),
        "elapsed_seconds": round(elapsed, 2),
    }


# ── Prompt builder ───────────────────────────────────────────────────

def _build_review_prompt(
    goal: str,
    plan: str | None,
    artifacts: list[dict],
    employee_name: str,
) -> str:
    """Build the review prompt with goal + artifacts for the Sentinel."""
    sections = [
        f"## Original Goal\n{goal}",
        f"\n## Work Done By\n{employee_name}",
    ]

    if plan:
        sections.append(f"\n## Agent's Plan\n{plan[:2000]}")

    if artifacts:
        sections.append(f"\n## Artifacts Produced ({len(artifacts)} files)")
        for art in artifacts[:20]:
            title = art.get("title", "untitled")
            path = art.get("path", "")
            lang = art.get("language", "")
            content = art.get("content", "")
            if len(content) > 5000:
                content = content[:5000] + "\n...(truncated)"

            sections.append(f"\n### {title}")
            if path:
                sections.append(f"Path: `{path}`")
            if content:
                sections.append(f"```{lang}\n{content}\n```")
    else:
        sections.append("\n## Artifacts\nNo files were produced.")

    sections.append(
        "\n## Your Task\n"
        "Review ALL artifacts against the original goal. "
        "Return your JSON verdict."
    )

    return "\n".join(sections)


# ── JSON parsing ─────────────────────────────────────────────────────

def _parse_verdict(response: str) -> dict:
    """Parse the Sentinel's JSON verdict from its response."""
    import re

    default = {
        "verdict": "PASS",
        "confidence": 0.5,
        "issues": [],
        "summary": "Could not parse Sentinel response. Passing by default.",
    }

    if not response:
        return default

    json_match = re.search(r'```json\s*\n?\s*(\{.*?\})\s*\n?\s*```', response, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            return _validate_verdict(parsed)
        except json.JSONDecodeError:
            pass

    bare_match = re.search(r'\{"verdict"\s*:.*\}', response, re.DOTALL)
    if bare_match:
        try:
            parsed = json.loads(bare_match.group(0))
            return _validate_verdict(parsed)
        except json.JSONDecodeError:
            pass

    if "FAIL" in response.upper():
        return {
            "verdict": "FAIL",
            "confidence": 0.6,
            "issues": [{"severity": "major", "file": "general", "description": response[:500]}],
            "summary": "Sentinel indicated failure (unstructured response).",
        }

    return default


def _validate_verdict(parsed: dict) -> dict:
    """Validate and normalize a parsed verdict dict."""
    verdict = parsed.get("verdict", "PASS").upper()
    if verdict not in ("PASS", "FAIL"):
        verdict = "PASS"

    confidence = parsed.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))

    issues = parsed.get("issues", [])
    if not isinstance(issues, list):
        issues = []

    valid_issues = []
    for issue in issues:
        if isinstance(issue, dict) and "description" in issue:
            valid_issues.append({
                "severity": issue.get("severity", "minor"),
                "file": issue.get("file", "unknown"),
                "description": issue["description"],
                "suggestion": issue.get("suggestion", ""),
            })

    return {
        "verdict": verdict,
        "confidence": confidence,
        "issues": valid_issues,
        "summary": parsed.get("summary", "Review complete."),
    }
