"""
Verification Proof Engine — making AI quality guarantee VISIBLE.

Every autonomous execution produces a scorecard: what Sentinel caught,
how quality changed from raw to verified, what it cost vs what it saved.

This is the proof that verification WORKS. Not a claim — a receipt.
The scorecard answers: "Would this have shipped with bugs without us?"
"""

import logging
from app.core.database import (
    create_scorecard,
    get_scorecard,
    get_user_scorecards,
    get_aggregate_proof_stats,
    get_execution_ledger,
    get_ledger_summary,
)

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS = {"critical": 10.0, "major": 3.0, "minor": 1.0}
ESTIMATED_BUG_COSTS = {"critical": 50.0, "major": 15.0, "minor": 3.0}
TOKENS_PER_DOLLAR = 1_000_000


async def generate_scorecard(
    execution_id: str,
    user_id: str,
    employee_id: str | None = None,
    goal: str | None = None,
    sentinel_result: dict | None = None,
) -> dict | None:
    existing = await get_scorecard(execution_id)
    if existing:
        return existing

    if not sentinel_result:
        sentinel_result = await _extract_sentinel_from_ledger(execution_id)
    if not sentinel_result:
        return None

    ledger_summary = await get_ledger_summary(execution_id)

    issues = sentinel_result.get("issues", [])
    tiers = sentinel_result.get("tiers", [])
    tiers_run = sentinel_result.get("tiers_run", len(tiers))

    issues_by_severity = {"critical": 0, "major": 0, "minor": 0}
    for issue in issues:
        sev = issue.get("severity", "minor")
        if sev in issues_by_severity:
            issues_by_severity[sev] += 1

    raw_score = _calculate_raw_score(issues)
    verified_score = _calculate_verified_score(sentinel_result)
    quality_delta = round(verified_score - raw_score, 2) if raw_score is not None else None

    verification_tokens = _sum_verification_tokens(ledger_summary)
    verification_cost = verification_tokens / TOKENS_PER_DOLLAR if verification_tokens else None

    bug_cost_saved = _estimate_bug_cost_saved(issues)

    would_have_shipped = (
        raw_score is not None
        and raw_score >= 0.6
        and issues_by_severity["critical"] > 0
    )

    final_verdict = _determine_verdict(sentinel_result, issues_by_severity)

    tier_results = {}
    for t in tiers:
        tier_num = t.get("tier", 0)
        tier_results[f"tier_{tier_num}"] = {
            "name": t.get("name", "unknown"),
            "verdict": t.get("verdict", "UNKNOWN"),
            "confidence": t.get("confidence", 0),
            "issues_found": len(t.get("issues", [])),
            "summary": t.get("summary", ""),
        }

    result = await create_scorecard(
        execution_id=execution_id,
        user_id=user_id,
        employee_id=employee_id,
        goal_summary=goal[:200] if goal else None,
        raw_quality_score=raw_score,
        verified_quality_score=verified_score,
        quality_delta=quality_delta,
        issues_caught=len(issues),
        issues_by_severity=issues_by_severity,
        sentinel_tiers_run=tiers_run,
        tier_results=tier_results,
        verification_cost_tokens=verification_tokens,
        verification_cost_usd=verification_cost,
        estimated_bug_cost_saved=bug_cost_saved,
        would_have_shipped_raw=would_have_shipped,
        final_verdict=final_verdict,
    )

    logger.info(
        f"Scorecard generated for {execution_id}: "
        f"raw={raw_score} verified={verified_score} delta={quality_delta} "
        f"issues={len(issues)} verdict={final_verdict}"
    )
    return await get_scorecard(execution_id)


def _calculate_raw_score(issues: list[dict]) -> float | None:
    if not issues:
        return 1.0

    total_penalty = sum(
        SEVERITY_WEIGHTS.get(i.get("severity", "minor"), 1.0)
        for i in issues
    )
    return round(max(0.0, 1.0 - (total_penalty / 30.0)), 2)


def _calculate_verified_score(sentinel_result: dict) -> float:
    verdict = sentinel_result.get("verdict", "PASS")
    confidence = sentinel_result.get("confidence", 0.5)

    if verdict == "PASS":
        return round(0.7 + (confidence * 0.3), 2)
    return round(max(0.1, confidence * 0.5), 2)


def _estimate_bug_cost_saved(issues: list[dict]) -> float:
    return round(sum(
        ESTIMATED_BUG_COSTS.get(i.get("severity", "minor"), 3.0)
        for i in issues
    ), 2)


def _sum_verification_tokens(ledger_summary: dict) -> int:
    return ledger_summary.get("total_tokens", 0) if ledger_summary else 0


def _determine_verdict(sentinel_result: dict, severity_counts: dict) -> str:
    verdict = sentinel_result.get("verdict", "PASS")
    if verdict == "FAIL":
        return "fail"
    if severity_counts.get("major", 0) > 0 or severity_counts.get("minor", 0) > 2:
        return "pass_with_warnings"
    return "pass"


async def _extract_sentinel_from_ledger(execution_id: str) -> dict | None:
    ledger = await get_execution_ledger(execution_id)
    if not ledger:
        return None

    import json
    for entry in reversed(ledger):
        if entry.get("action_type") == "sentinel_verification":
            evidence_raw = entry.get("evidence")
            if isinstance(evidence_raw, str):
                try:
                    return json.loads(evidence_raw)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif isinstance(evidence_raw, dict):
                return evidence_raw
    return None


async def get_proof(execution_id: str) -> dict | None:
    return await get_scorecard(execution_id)


async def get_user_proof_dashboard(user_id: str, limit: int = 50) -> dict:
    scorecards = await get_user_scorecards(user_id, limit=limit)
    aggregate = await get_aggregate_proof_stats(user_id)
    return {
        "scorecards": scorecards,
        "aggregate": aggregate,
    }
