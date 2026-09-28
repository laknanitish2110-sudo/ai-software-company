"""
Action Ledger Service — the commit primitive for ARIA's AI Action Infrastructure.

Every meaningful action during an autonomous execution produces a causal record:
intent → preconditions → execution → observation → verification → COMMIT/ROLLBACK

This is NOT a log. Logs record what happened. The ledger records WHY it happened,
what EVIDENCE supports it, and whether the state transition was VERIFIED.
"""

import json
import time
from app.core.database import create_ledger_entry, get_execution_ledger, get_ledger_summary


def _json_dump(obj) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    return json.dumps(obj)


async def record_phase_transition(
    execution_id: str,
    iteration: int,
    from_phase: str,
    to_phase: str,
    actor: str,
    reason: str | None = None,
    confidence: float | None = None,
    preconditions: list[str] | None = None,
    tokens_used: int = 0,
    duration_ms: int | None = None,
) -> dict:
    return await create_ledger_entry(
        execution_id=execution_id,
        iteration=iteration,
        phase=to_phase,
        action_type="phase_transition",
        intent=f"Transition from {from_phase} to {to_phase}",
        actor=actor,
        authority="execution_policy",
        preconditions=_json_dump(preconditions or [f"{from_phase} completed"]),
        evidence=_json_dump({
            "from_phase": from_phase,
            "to_phase": to_phase,
            "confidence": confidence,
            "reason": reason,
        }),
        expected_effects=f"Execution enters {to_phase} phase",
        actual_effects=f"State = {to_phase}",
        commit_decision="committed",
        tokens_used=tokens_used,
        duration_ms=duration_ms,
    )


async def record_tool_execution(
    execution_id: str,
    iteration: int,
    phase: str,
    actor: str,
    tool_name: str,
    tool_input: str | None = None,
    tool_output: str | None = None,
    success: bool = True,
    duration_ms: int | None = None,
) -> dict:
    return await create_ledger_entry(
        execution_id=execution_id,
        iteration=iteration,
        phase=phase,
        action_type="tool_execution",
        intent=f"Execute tool: {tool_name}",
        actor=actor,
        authority="tool_permission",
        preconditions=_json_dump([f"Tool '{tool_name}' is permitted for role"]),
        evidence=_json_dump({
            "tool": tool_name,
            "input_summary": (tool_input or "")[:500],
            "output_summary": (tool_output or "")[:500],
            "success": success,
        }),
        expected_effects=f"Tool '{tool_name}' produces result",
        actual_effects=f"Tool {'succeeded' if success else 'failed'}",
        commit_decision="committed" if success else "rolled_back",
        duration_ms=duration_ms,
    )


async def record_sentinel_verdict(
    execution_id: str,
    iteration: int,
    phase: str,
    actor: str,
    tier: int,
    verdict: str,
    issues: list[dict] | None = None,
    tiers_run: int = 1,
    elapsed_ms: int | None = None,
    tokens_used: int = 0,
) -> dict:
    passed = verdict.upper() == "PASS"
    return await create_ledger_entry(
        execution_id=execution_id,
        iteration=iteration,
        phase=phase,
        action_type="sentinel_verification",
        intent="Independent verification of execution output",
        actor=f"Sentinel (Tier {tier})",
        authority="sentinel_protocol",
        preconditions=_json_dump(["Output produced", "QA phase reached"]),
        evidence=_json_dump({
            "verdict": verdict,
            "tier": tier,
            "tiers_run": tiers_run,
            "issues_count": len(issues) if issues else 0,
            "issues": issues[:5] if issues else [],
        }),
        expected_effects="Output verified as correct",
        actual_effects=f"Sentinel verdict: {verdict}" + (
            f" — {len(issues)} issues found" if issues else ""
        ),
        verification_result=_json_dump({
            "passed": passed,
            "verdict": verdict,
            "issues": issues,
        }),
        commit_decision="committed" if passed else "rolled_back",
        tokens_used=tokens_used,
        duration_ms=elapsed_ms,
    )


async def record_delegation(
    execution_id: str,
    iteration: int,
    phase: str,
    from_actor: str,
    to_actor: str,
    task_description: str,
    delegation_id: str | None = None,
) -> dict:
    return await create_ledger_entry(
        execution_id=execution_id,
        iteration=iteration,
        phase=phase,
        action_type="delegation",
        intent=f"Delegate task to {to_actor}",
        actor=from_actor,
        authority=f"delegation_from:{from_actor}",
        preconditions=_json_dump([
            f"{from_actor} authorized to delegate",
            f"{to_actor} available and capable",
        ]),
        evidence=_json_dump({
            "delegation_id": delegation_id,
            "from": from_actor,
            "to": to_actor,
            "task": task_description[:500],
        }),
        expected_effects=f"{to_actor} completes delegated task",
        actual_effects="Delegation created, awaiting completion",
        commit_decision="pending",
    )


async def record_llm_reasoning(
    execution_id: str,
    iteration: int,
    phase: str,
    actor: str,
    input_summary: str | None = None,
    output_summary: str | None = None,
    tokens_used: int = 0,
    duration_ms: int | None = None,
    model: str | None = None,
) -> dict:
    return await create_ledger_entry(
        execution_id=execution_id,
        iteration=iteration,
        phase=phase,
        action_type="llm_reasoning",
        intent=f"LLM reasoning during {phase}",
        actor=actor,
        authority="execution_controller",
        evidence=_json_dump({
            "input_summary": (input_summary or "")[:300],
            "output_summary": (output_summary or "")[:300],
            "model": model,
        }),
        actual_effects=f"Produced reasoning output ({tokens_used} tokens)",
        commit_decision="committed",
        tokens_used=tokens_used,
        duration_ms=duration_ms,
    )


async def record_execution_start(
    execution_id: str,
    actor: str,
    goal: str,
    policy_name: str,
) -> dict:
    return await create_ledger_entry(
        execution_id=execution_id,
        iteration=0,
        phase="PLANNING",
        action_type="execution_start",
        intent=f"Begin autonomous execution: {goal[:200]}",
        actor=actor,
        authority="user_goal",
        preconditions=_json_dump([
            "Employee available",
            "Execution policy loaded",
            "Budget within limits",
        ]),
        evidence=_json_dump({
            "goal": goal[:500],
            "policy": policy_name,
        }),
        expected_effects="Execution begins PLANNING phase",
        actual_effects="Execution started",
        commit_decision="committed",
    )


async def record_execution_complete(
    execution_id: str,
    iteration: int,
    actor: str,
    final_state: str,
    artifacts_count: int = 0,
    total_tokens: int = 0,
    total_duration_ms: int | None = None,
) -> dict:
    success = final_state == "COMPLETED"
    return await create_ledger_entry(
        execution_id=execution_id,
        iteration=iteration,
        phase=final_state,
        action_type="execution_complete",
        intent="Finalize execution",
        actor=actor,
        authority="execution_controller",
        preconditions=_json_dump([
            "All phases completed" if success else "Terminal state reached",
        ]),
        evidence=_json_dump({
            "final_state": final_state,
            "artifacts_produced": artifacts_count,
            "total_tokens": total_tokens,
            "total_duration_ms": total_duration_ms,
        }),
        expected_effects="Execution reaches terminal state",
        actual_effects=f"Execution {final_state.lower()} with {artifacts_count} artifacts",
        commit_decision="committed" if success else "rolled_back",
        tokens_used=total_tokens,
        duration_ms=total_duration_ms,
    )


async def get_ledger(execution_id: str) -> list[dict]:
    return await get_execution_ledger(execution_id)


async def get_summary(execution_id: str) -> dict:
    return await get_ledger_summary(execution_id)
