"""
State Truth Engine — Memory ≠ Truth.

Upgrades agent state from "what agent remembers" to "what is verifiably true
right now." Every tool output, every LLM claim, every execution result is a
CLAIM about the world — not a fact. Claims are UNVERIFIED until evidence
promotes them.

Status lifecycle:
  unverified → verified (Sentinel passes, evidence confirms)
  unverified → contradicted (conflicts with verified claim)
  verified → stale (TTL expired, needs re-verification)
  verified → superseded (newer verified claim replaces it)
  any → contradicted (Sentinel fails, evidence disproves)

This is Gap A from the deep thesis: "What is the actual state of the world?"
"""

import logging
from datetime import datetime, timedelta, timezone

from app.core.database import (
    create_state_claim,
    verify_claim,
    invalidate_claim,
    supersede_claim,
    get_claims_for_execution,
    get_verified_state,
    get_employee_claims,
    detect_stale_claims,
    find_contradictions,
    get_truth_summary,
    now_iso,
)

logger = logging.getLogger(__name__)

CLAIM_TTL_HOURS = {
    "tool_output": 24,
    "file_created": 168,
    "api_response": 1,
    "computation_result": 168,
    "web_search": 12,
    "user_instruction": 720,
    "sentinel_verdict": 168,
}


async def record_tool_claim(
    employee_id: str,
    user_id: str,
    execution_id: str,
    tool_name: str,
    claim_key: str,
    claim_value: str,
    ledger_id: str | None = None,
    evidence: dict | None = None,
) -> dict:
    ttl = CLAIM_TTL_HOURS.get("tool_output", 24)
    expires = (datetime.now(timezone.utc) + timedelta(hours=ttl)).isoformat()

    contradictions = await find_contradictions(employee_id, claim_key, claim_value)

    for old in contradictions:
        if old["status"] == "verified":
            logger.info(
                f"New claim '{claim_key}' contradicts verified claim {old['id']}. "
                f"Old='{old['claim_value'][:50]}' New='{claim_value[:50]}'"
            )

    result = await create_state_claim(
        employee_id=employee_id,
        user_id=user_id,
        claim_type="tool_output",
        claim_key=claim_key,
        claim_value=claim_value,
        execution_id=execution_id,
        source_action=tool_name,
        source_ledger_id=ledger_id,
        evidence=evidence,
        confidence=0.5,
        status="unverified",
        expires_at=expires,
    )

    for old in contradictions:
        if old["status"] == "unverified":
            await supersede_claim(old["id"], result["id"])

    return result


async def record_execution_claim(
    employee_id: str,
    user_id: str,
    execution_id: str,
    claim_key: str,
    claim_value: str,
    claim_type: str = "computation_result",
    evidence: dict | None = None,
) -> dict:
    ttl = CLAIM_TTL_HOURS.get(claim_type, 24)
    expires = (datetime.now(timezone.utc) + timedelta(hours=ttl)).isoformat()

    return await create_state_claim(
        employee_id=employee_id,
        user_id=user_id,
        claim_type=claim_type,
        claim_key=claim_key,
        claim_value=claim_value,
        execution_id=execution_id,
        evidence=evidence,
        confidence=0.5,
        status="unverified",
        expires_at=expires,
    )


async def promote_execution_claims(execution_id: str, verified_by: str = "sentinel") -> int:
    claims = await get_claims_for_execution(execution_id)
    promoted = 0
    for claim in claims:
        if claim["status"] == "unverified":
            await verify_claim(claim["id"], verified_by=verified_by, confidence=0.85)
            promoted += 1
    logger.info(f"Promoted {promoted}/{len(claims)} claims for execution {execution_id}")
    return promoted


async def reject_execution_claims(execution_id: str, reason: str = "sentinel_fail") -> int:
    claims = await get_claims_for_execution(execution_id)
    rejected = 0
    for claim in claims:
        if claim["status"] == "unverified":
            await invalidate_claim(claim["id"], reason="contradicted")
            rejected += 1
    logger.info(f"Rejected {rejected}/{len(claims)} claims for execution {execution_id}")
    return rejected


async def get_truth(employee_id: str) -> dict:
    await detect_stale_claims(employee_id)
    verified = await get_verified_state(employee_id)
    summary = await get_truth_summary(employee_id)

    truth_map: dict[str, dict] = {}
    for claim in verified:
        key = claim["claim_key"]
        if key not in truth_map:
            truth_map[key] = {
                "key": key,
                "value": claim["claim_value"],
                "confidence": claim["confidence"],
                "verified_at": claim["verified_at"],
                "claim_type": claim["claim_type"],
                "expires_at": claim.get("expires_at"),
            }

    return {
        "verified_facts": list(truth_map.values()),
        "summary": summary,
    }


async def get_stale_claims(employee_id: str) -> list[dict]:
    return await detect_stale_claims(employee_id)


async def get_execution_truth(execution_id: str) -> dict:
    claims = await get_claims_for_execution(execution_id)
    by_status: dict[str, list] = {"verified": [], "unverified": [], "contradicted": [], "stale": [], "superseded": []}
    for c in claims:
        bucket = by_status.get(c["status"], [])
        bucket.append(c)

    return {
        "execution_id": execution_id,
        "claims": claims,
        "by_status": {k: len(v) for k, v in by_status.items()},
        "total": len(claims),
        "verified_count": len(by_status["verified"]),
        "trust_ratio": round(len(by_status["verified"]) / max(len(claims), 1), 2),
    }
