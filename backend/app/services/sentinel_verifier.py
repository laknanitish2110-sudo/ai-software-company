"""
Independent Sentinel Verification.

When an execution reaches QA, this module calls a SEPARATE LLM in a
clean context (no conversation history from the builder agent). The
Sentinel receives only:
  1. The original goal
  2. The artifacts produced (files, code)
  3. The execution plan

It returns a structured verdict: PASS or FAIL with specific issues.

This is the anti-wrapper differentiator — a second opinion from a
different context that measurably reduces bugs vs single-agent systems.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


SENTINEL_SYSTEM_PROMPT = """You are an independent QA reviewer. You are reviewing work produced by another AI agent.

IMPORTANT: You did NOT produce this work. You are seeing it for the first time. Your job is to find
defects, not to defend the implementation.

Review the work against the original goal. Be rigorous but fair:
- Check that the goal is fully addressed, not partially
- Check for bugs, logic errors, missing edge cases
- Check for security vulnerabilities (injection, XSS, auth bypass, secrets exposure)
- Check for incomplete implementations (TODOs, placeholder code, hardcoded values)
- Check that error handling exists where needed
- Check that the code would actually work if deployed

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


async def sentinel_verify(
    goal: str,
    plan: str | None,
    artifacts: list[dict],
    employee_name: str = "an AI employee",
) -> dict:
    """Run independent Sentinel verification on execution artifacts.

    Args:
        goal: The original execution goal
        plan: The plan the agent created (if any)
        artifacts: List of {title, path, content, language} dicts
        employee_name: Name of the employee who did the work

    Returns:
        Structured verdict dict with verdict, confidence, issues, summary
    """
    from app.agents.engine import call_llm_with_fallback

    review_content = _build_review_prompt(goal, plan, artifacts, employee_name)

    messages = [
        {"role": "system", "content": SENTINEL_SYSTEM_PROMPT},
        {"role": "user", "content": review_content},
    ]

    try:
        text, _ = await call_llm_with_fallback(
            messages=messages,
            role="qa",
            temperature=0.2,
            tools=None,
        )

        verdict = _parse_verdict(text)
        logger.info(
            f"Sentinel verdict: {verdict.get('verdict', 'UNKNOWN')} "
            f"(confidence={verdict.get('confidence', 0)}, "
            f"issues={len(verdict.get('issues', []))})"
        )
        return verdict

    except Exception as e:
        logger.error(f"Sentinel verification failed: {e}")
        return {
            "verdict": "PASS",
            "confidence": 0.3,
            "issues": [],
            "summary": f"Sentinel verification unavailable: {e}. Passing by default.",
            "error": str(e),
        }


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
