"""
Experience Compiler — The Moat.

Execution trajectories + failure patterns compiled into reusable procedures.
ARIA gets measurably smarter with every run. The accumulated operational
intelligence is the thing that's hard to copy.

Pattern types:
  - tool_sequence: which tools were used and in what order
  - failure_mode: what failed and why
  - quality_pattern: what Sentinel caught and how severe
  - delegation_pattern: how work was split across agents
  - recovery_pattern: what recovery strategy worked

Procedure types:
  - success_pattern: replicate what worked
  - failure_avoidance: pre-check to prevent known failures
  - optimization: skip unnecessary steps based on history
  - pre_check: validate preconditions before starting
"""

import hashlib
import json
import logging
from collections import Counter

from app.core.database import (
    create_pattern,
    get_patterns_for_employee,
    get_patterns_by_key,
    create_procedure,
    get_procedures_for_employee,
    record_procedure_application,
    get_experience_summary,
)

logger = logging.getLogger(__name__)

MIN_PATTERNS_FOR_COMPILATION = 3
CONFIDENCE_THRESHOLD = 0.6


async def extract_patterns(
    execution_id: str,
    employee_id: str,
    user_id: str,
    outcome: str,
    goal: str | None = None,
) -> list[dict]:
    patterns = []

    try:
        from app.core.database import get_ledger_entries
        entries = await get_ledger_entries(execution_id, limit=100)
    except Exception:
        entries = []

    if entries:
        tool_seq = [e["action_type"] for e in entries if e.get("action_type")]
        if tool_seq:
            key = _pattern_key("tool_sequence", tool_seq)
            p = await create_pattern(
                execution_id=execution_id,
                employee_id=employee_id,
                user_id=user_id,
                pattern_type="tool_sequence",
                pattern_key=key,
                pattern_data=json.dumps({
                    "sequence": tool_seq,
                    "length": len(tool_seq),
                    "goal_preview": (goal or "")[:200],
                }),
                outcome=outcome,
            )
            patterns.append(p)

        sentinel_entries = [e for e in entries if e.get("action_type") == "sentinel_verification"]
        if sentinel_entries:
            for se in sentinel_entries:
                meta = _safe_json(se.get("metadata"))
                verdict = meta.get("verdict", "unknown") if meta else "unknown"
                issues = meta.get("issues_found", 0) if meta else 0
                key = _pattern_key("quality_pattern", [verdict, str(issues)])
                p = await create_pattern(
                    execution_id=execution_id,
                    employee_id=employee_id,
                    user_id=user_id,
                    pattern_type="quality_pattern",
                    pattern_key=key,
                    pattern_data=json.dumps({
                        "verdict": verdict,
                        "issues_found": issues,
                        "goal_preview": (goal or "")[:200],
                    }),
                    outcome=outcome,
                )
                patterns.append(p)

        delegation_entries = [e for e in entries if e.get("action_type") == "delegation"]
        if delegation_entries:
            delegates = [e.get("actor", "unknown") for e in delegation_entries]
            key = _pattern_key("delegation_pattern", delegates)
            p = await create_pattern(
                execution_id=execution_id,
                employee_id=employee_id,
                user_id=user_id,
                pattern_type="delegation_pattern",
                pattern_key=key,
                pattern_data=json.dumps({
                    "delegates": delegates,
                    "count": len(delegates),
                    "goal_preview": (goal or "")[:200],
                }),
                outcome=outcome,
            )
            patterns.append(p)

    if outcome == "failure":
        try:
            from app.core.database import get_recovery_attempts
            attempts = await get_recovery_attempts(execution_id)
            for att in attempts:
                key = _pattern_key("failure_mode", [att.get("failure_type", "unknown")])
                p = await create_pattern(
                    execution_id=execution_id,
                    employee_id=employee_id,
                    user_id=user_id,
                    pattern_type="failure_mode",
                    pattern_key=key,
                    pattern_data=json.dumps({
                        "failure_type": att.get("failure_type"),
                        "failure_detail": (att.get("failure_detail") or "")[:300],
                        "strategy": att.get("strategy"),
                        "outcome": att.get("outcome"),
                    }),
                    outcome="failure",
                )
                patterns.append(p)

                if att.get("outcome") == "recovered":
                    rkey = _pattern_key("recovery_pattern", [att.get("failure_type", ""), att.get("strategy", "")])
                    rp = await create_pattern(
                        execution_id=execution_id,
                        employee_id=employee_id,
                        user_id=user_id,
                        pattern_type="recovery_pattern",
                        pattern_key=rkey,
                        pattern_data=json.dumps({
                            "failure_type": att.get("failure_type"),
                            "strategy": att.get("strategy"),
                            "recovered": True,
                        }),
                        outcome="success",
                    )
                    patterns.append(rp)
        except Exception:
            pass

    logger.info(f"Extracted {len(patterns)} patterns from execution {execution_id}")
    return patterns


async def compile_procedures(employee_id: str, user_id: str) -> list[dict]:
    all_patterns = await get_patterns_for_employee(employee_id, limit=200)
    if len(all_patterns) < MIN_PATTERNS_FOR_COMPILATION:
        return []

    key_groups: dict[str, list[dict]] = {}
    for p in all_patterns:
        key_groups.setdefault(p["pattern_key"], []).append(p)

    new_procedures = []
    existing = await get_procedures_for_employee(employee_id)
    existing_triggers = {p["trigger_condition"] for p in existing}

    for key, group in key_groups.items():
        if len(group) < MIN_PATTERNS_FOR_COMPILATION:
            continue

        outcomes = Counter(p["outcome"] for p in group)
        total = len(group)
        successes = outcomes.get("success", 0)
        failures = outcomes.get("failure", 0)
        success_rate = successes / max(total, 1)

        pattern_type = group[0]["pattern_type"]
        sample_data = _safe_json(group[0].get("pattern_data"))

        if success_rate >= 0.7 and pattern_type == "tool_sequence":
            trigger = f"tool_sequence:{key}"
            if trigger in existing_triggers:
                continue
            proc = await create_procedure(
                employee_id=employee_id,
                user_id=user_id,
                procedure_type="success_pattern",
                trigger_condition=trigger,
                procedure_steps=json.dumps({
                    "description": f"Reliable tool sequence (seen {total}x, {success_rate:.0%} success)",
                    "sequence": sample_data.get("sequence", []) if sample_data else [],
                    "recommendation": "follow_this_sequence",
                }),
                source_executions=json.dumps([p["execution_id"] for p in group[:10]]),
                confidence=min(0.95, success_rate * (1 - 1 / total)),
            )
            new_procedures.append(proc)

        if failures >= MIN_PATTERNS_FOR_COMPILATION and pattern_type == "failure_mode":
            trigger = f"failure_avoidance:{key}"
            if trigger in existing_triggers:
                continue
            proc = await create_procedure(
                employee_id=employee_id,
                user_id=user_id,
                procedure_type="failure_avoidance",
                trigger_condition=trigger,
                procedure_steps=json.dumps({
                    "description": f"Known failure mode (seen {failures}x)",
                    "failure_type": sample_data.get("failure_type") if sample_data else None,
                    "recommendation": "pre_check_before_starting",
                    "typical_detail": (sample_data.get("failure_detail", "") if sample_data else "")[:200],
                }),
                source_executions=json.dumps([p["execution_id"] for p in group[:10]]),
                confidence=min(0.9, failures / total),
            )
            new_procedures.append(proc)

        if pattern_type == "recovery_pattern" and successes >= 2:
            trigger = f"recovery_strategy:{key}"
            if trigger in existing_triggers:
                continue
            proc = await create_procedure(
                employee_id=employee_id,
                user_id=user_id,
                procedure_type="optimization",
                trigger_condition=trigger,
                procedure_steps=json.dumps({
                    "description": f"Proven recovery strategy (worked {successes}x)",
                    "strategy": sample_data.get("strategy") if sample_data else None,
                    "for_failure_type": sample_data.get("failure_type") if sample_data else None,
                    "recommendation": "use_this_strategy_first",
                }),
                source_executions=json.dumps([p["execution_id"] for p in group[:10]]),
                confidence=min(0.85, success_rate),
            )
            new_procedures.append(proc)

        if pattern_type == "quality_pattern" and total >= MIN_PATTERNS_FOR_COMPILATION:
            trigger = f"quality_precheck:{key}"
            if trigger in existing_triggers:
                continue
            proc = await create_procedure(
                employee_id=employee_id,
                user_id=user_id,
                procedure_type="pre_check",
                trigger_condition=trigger,
                procedure_steps=json.dumps({
                    "description": f"Quality pre-check based on {total} past verifications",
                    "typical_verdict": sample_data.get("verdict") if sample_data else None,
                    "typical_issues": sample_data.get("issues_found", 0) if sample_data else 0,
                    "recommendation": "focus_sentinel_on_known_issues",
                }),
                source_executions=json.dumps([p["execution_id"] for p in group[:10]]),
                confidence=0.6,
            )
            new_procedures.append(proc)

    logger.info(f"Compiled {len(new_procedures)} new procedures for employee {employee_id}")
    return new_procedures


async def get_recommendations(employee_id: str, goal: str | None = None) -> dict:
    procedures = await get_procedures_for_employee(employee_id)
    if not procedures:
        return {"procedures": [], "intelligence_level": "novice", "total_procedures": 0}

    relevant = []
    for proc in procedures:
        if proc.get("confidence", 0) < CONFIDENCE_THRESHOLD:
            continue
        relevant.append({
            "id": proc["id"],
            "type": proc["procedure_type"],
            "trigger": proc["trigger_condition"],
            "steps": _safe_json(proc.get("procedure_steps")),
            "confidence": proc.get("confidence", 0),
            "success_rate": proc.get("success_rate", 0),
            "times_applied": proc.get("times_applied", 0),
        })

    relevant.sort(key=lambda x: x["confidence"], reverse=True)

    total = len(procedures)
    level = "novice"
    if total >= 20:
        level = "expert"
    elif total >= 10:
        level = "proficient"
    elif total >= 5:
        level = "competent"
    elif total >= 2:
        level = "learning"

    return {
        "procedures": relevant[:10],
        "intelligence_level": level,
        "total_procedures": total,
    }


async def record_application(procedure_id: str, succeeded: bool) -> dict:
    return await record_procedure_application(procedure_id, succeeded)


async def get_experience(employee_id: str) -> dict:
    summary = await get_experience_summary(employee_id)
    procedures = await get_procedures_for_employee(employee_id)

    total_patterns = summary.get("total_patterns", 0) or 0
    total_procs = summary.get("total_procedures", 0) or 0

    level = "novice"
    if total_procs >= 20:
        level = "expert"
    elif total_procs >= 10:
        level = "proficient"
    elif total_procs >= 5:
        level = "competent"
    elif total_procs >= 2:
        level = "learning"

    return {
        "employee_id": employee_id,
        "intelligence_level": level,
        "patterns": {
            "total": total_patterns,
            "successes": summary.get("success_patterns", 0) or 0,
            "failures": summary.get("failure_patterns", 0) or 0,
            "types_seen": summary.get("pattern_types", 0) or 0,
            "executions_analyzed": summary.get("executions_analyzed", 0) or 0,
        },
        "procedures": {
            "total": total_procs,
            "active": summary.get("active_procedures", 0) or 0,
            "total_applications": summary.get("total_applications", 0) or 0,
            "total_successes": summary.get("total_successes", 0) or 0,
            "avg_confidence": round(summary.get("avg_confidence", 0) or 0, 2),
            "avg_success_rate": round(summary.get("avg_success_rate", 0) or 0, 2),
        },
        "compiled_procedures": [
            {
                "id": p["id"],
                "type": p["procedure_type"],
                "trigger": p["trigger_condition"],
                "steps": _safe_json(p.get("procedure_steps")),
                "confidence": p.get("confidence", 0),
                "success_rate": p.get("success_rate", 0),
                "times_applied": p.get("times_applied", 0),
                "times_succeeded": p.get("times_succeeded", 0),
                "status": p.get("status", "active"),
                "created_at": p.get("created_at"),
            }
            for p in procedures
        ],
    }


def _pattern_key(pattern_type: str, components: list[str]) -> str:
    raw = f"{pattern_type}:" + "|".join(str(c) for c in components)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _safe_json(val) -> dict | None:
    if not val:
        return None
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None
