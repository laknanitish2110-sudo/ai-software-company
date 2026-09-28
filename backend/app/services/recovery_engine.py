"""
Recovery Engine — Intelligent checkpoint-based recovery, not blind retry.

When something fails, the Recovery Engine:
1. DIAGNOSES the failure (what type, where, how severe)
2. FINDS the last verified checkpoint (not "start over")
3. DETERMINES compensation actions (what needs undoing)
4. RESUMES from verified state (not from scratch)

This is Gap D from the deep thesis: "How do I get back to a good state?"
The answer is never retry(). It's: checkpoint → diagnose → plan → recover.
"""

import logging
import time

from app.core.database import (
    create_checkpoint,
    get_checkpoints,
    get_latest_checkpoint,
    create_recovery_attempt,
    resolve_recovery_attempt,
    get_recovery_attempts,
    get_verified_state,
    get_claims_for_execution,
    now_iso,
)

logger = logging.getLogger(__name__)

FAILURE_CATEGORIES = {
    "sentinel_fail": {"severity": "high", "default_strategy": "rollback_and_repair"},
    "tool_error": {"severity": "medium", "default_strategy": "retry_with_context"},
    "budget_exceeded": {"severity": "critical", "default_strategy": "abort"},
    "timeout": {"severity": "high", "default_strategy": "checkpoint_resume"},
    "llm_error": {"severity": "medium", "default_strategy": "retry_with_context"},
    "delegation_fail": {"severity": "medium", "default_strategy": "rollback_and_repair"},
    "unknown": {"severity": "high", "default_strategy": "abort"},
}

MAX_RECOVERY_ATTEMPTS = 3


async def save_checkpoint(
    execution_id: str,
    employee_id: str,
    phase: str,
    iteration: int,
    checkpoint_type: str = "auto",
) -> dict:
    verified = await get_verified_state(employee_id)
    verified_snapshot = [
        {"key": c["claim_key"], "value": c["claim_value"][:500], "confidence": c["confidence"]}
        for c in verified[:50]
    ]

    return await create_checkpoint(
        execution_id=execution_id,
        employee_id=employee_id,
        phase=phase,
        iteration=iteration,
        checkpoint_type=checkpoint_type,
        verified_state={"claims": verified_snapshot, "count": len(verified)},
        metadata={"timestamp": now_iso()},
    )


async def diagnose_failure(
    execution_id: str,
    error: str,
    phase: str | None = None,
    iteration: int | None = None,
) -> dict:
    failure_type = _classify_failure(error)
    category = FAILURE_CATEGORIES.get(failure_type, FAILURE_CATEGORIES["unknown"])

    checkpoints = await get_checkpoints(execution_id)
    prior_attempts = await get_recovery_attempts(execution_id)
    failed_attempts = [a for a in prior_attempts if a["outcome"] == "failed"]

    if len(failed_attempts) >= MAX_RECOVERY_ATTEMPTS:
        strategy = "abort"
        reason = f"Max recovery attempts ({MAX_RECOVERY_ATTEMPTS}) reached"
    elif category["severity"] == "critical":
        strategy = "abort"
        reason = f"Critical failure: {failure_type}"
    elif not checkpoints:
        strategy = "retry_from_start" if len(failed_attempts) < 1 else "abort"
        reason = "No checkpoints available" + (" — one retry allowed" if strategy != "abort" else "")
    else:
        strategy = category["default_strategy"]
        reason = f"{failure_type} with {len(checkpoints)} checkpoint(s) available"

    rollback_target = checkpoints[0] if checkpoints and strategy in ("rollback_and_repair", "checkpoint_resume") else None

    diagnosis = {
        "failure_type": failure_type,
        "severity": category["severity"],
        "strategy": strategy,
        "reason": reason,
        "error_summary": error[:500],
        "failure_phase": phase,
        "failure_iteration": iteration,
        "rollback_target": rollback_target,
        "prior_attempts": len(prior_attempts),
        "failed_attempts": len(failed_attempts),
        "checkpoints_available": len(checkpoints),
    }

    logger.info(
        f"Recovery diagnosis for {execution_id}: "
        f"type={failure_type} severity={category['severity']} strategy={strategy}"
    )
    return diagnosis


async def attempt_recovery(
    execution_id: str,
    diagnosis: dict,
) -> dict:
    start = time.time()
    strategy = diagnosis["strategy"]
    rollback_target = diagnosis.get("rollback_target")

    attempt = await create_recovery_attempt(
        execution_id=execution_id,
        failure_type=diagnosis["failure_type"],
        failure_detail=diagnosis.get("error_summary"),
        failure_phase=diagnosis.get("failure_phase"),
        failure_iteration=diagnosis.get("failure_iteration"),
        strategy=strategy,
        checkpoint_id=rollback_target["id"] if rollback_target else None,
        actions_taken={"strategy": strategy, "diagnosis": diagnosis["reason"]},
    )

    if strategy == "abort":
        duration = int((time.time() - start) * 1000)
        await resolve_recovery_attempt(attempt["id"], outcome="aborted", duration_ms=duration)
        return {
            "attempt_id": attempt["id"],
            "strategy": "abort",
            "outcome": "aborted",
            "reason": diagnosis["reason"],
            "resume_phase": None,
            "resume_iteration": None,
        }

    if strategy == "retry_from_start":
        duration = int((time.time() - start) * 1000)
        await resolve_recovery_attempt(attempt["id"], outcome="pending", duration_ms=duration)
        return {
            "attempt_id": attempt["id"],
            "strategy": "retry_from_start",
            "outcome": "pending",
            "reason": "Retrying from PLANNING phase",
            "resume_phase": "PLANNING",
            "resume_iteration": 0,
        }

    if strategy in ("rollback_and_repair", "checkpoint_resume") and rollback_target:
        duration = int((time.time() - start) * 1000)
        await resolve_recovery_attempt(attempt["id"], outcome="pending", duration_ms=duration)
        return {
            "attempt_id": attempt["id"],
            "strategy": strategy,
            "outcome": "pending",
            "reason": f"Rolling back to checkpoint at {rollback_target['phase']} iteration {rollback_target['iteration']}",
            "resume_phase": rollback_target["phase"],
            "resume_iteration": rollback_target["iteration"],
            "checkpoint": rollback_target,
        }

    if strategy == "retry_with_context":
        duration = int((time.time() - start) * 1000)
        await resolve_recovery_attempt(attempt["id"], outcome="pending", duration_ms=duration)
        return {
            "attempt_id": attempt["id"],
            "strategy": "retry_with_context",
            "outcome": "pending",
            "reason": f"Retrying with failure context: {diagnosis['failure_type']}",
            "resume_phase": diagnosis.get("failure_phase"),
            "resume_iteration": diagnosis.get("failure_iteration"),
            "failure_context": diagnosis.get("error_summary"),
        }

    duration = int((time.time() - start) * 1000)
    await resolve_recovery_attempt(attempt["id"], outcome="aborted", duration_ms=duration)
    return {
        "attempt_id": attempt["id"],
        "strategy": "abort",
        "outcome": "aborted",
        "reason": f"Unknown strategy: {strategy}",
        "resume_phase": None,
        "resume_iteration": None,
    }


async def get_recovery_history(execution_id: str) -> dict:
    checkpoints = await get_checkpoints(execution_id)
    attempts = await get_recovery_attempts(execution_id)

    return {
        "execution_id": execution_id,
        "checkpoints": checkpoints,
        "recovery_attempts": attempts,
        "checkpoint_count": len(checkpoints),
        "attempt_count": len(attempts),
        "successful_recoveries": len([a for a in attempts if a["outcome"] == "recovered"]),
        "failed_recoveries": len([a for a in attempts if a["outcome"] == "failed"]),
        "aborted": len([a for a in attempts if a["outcome"] == "aborted"]),
    }


def _classify_failure(error: str) -> str:
    error_lower = error.lower()
    if "sentinel" in error_lower or "verification" in error_lower or "qa" in error_lower:
        return "sentinel_fail"
    if "budget" in error_lower or "token" in error_lower or "cost" in error_lower:
        return "budget_exceeded"
    if "timeout" in error_lower or "time limit" in error_lower:
        return "timeout"
    if "tool" in error_lower or "execute_tool" in error_lower:
        return "tool_error"
    if "delegat" in error_lower:
        return "delegation_fail"
    if "llm" in error_lower or "api" in error_lower or "model" in error_lower:
        return "llm_error"
    return "unknown"
