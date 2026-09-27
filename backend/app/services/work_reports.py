"""
"While You Were Away" Work Report Generator.

Aggregates autonomous execution data into structured reports showing what
the AI team accomplished while the user was offline. Groups by employee,
includes artifacts produced, phases completed, QA results, and costs.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import (
    get_db,
    list_autonomous_executions,
    list_execution_artifacts,
    get_execution_logs,
)

logger = logging.getLogger(__name__)


async def generate_work_report(
    user_id: str,
    since: str | None = None,
    hours: int = 24,
) -> dict:
    """Generate a structured work report for everything that happened.

    Args:
        user_id: The user to generate the report for.
        since: ISO timestamp to look back from. Defaults to `hours` ago.
        hours: Hours to look back if `since` is not provided.

    Returns:
        A structured report dict with employee summaries, totals, and timeline.
    """
    if since:
        cutoff = since
    else:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT ae.*, e.name as employee_name, e.role as employee_role,
                      e.avatar_url as employee_avatar
               FROM autonomous_executions ae
               JOIN employees e ON e.id = ae.employee_id
               WHERE ae.user_id = ?
                 AND ae.created_at >= ?
               ORDER BY ae.created_at DESC""",
            (user_id, cutoff),
        )
        executions = await cursor.fetchall()
    finally:
        await db.close()

    if not executions:
        return {
            "period": {"since": cutoff, "hours": hours},
            "summary": {
                "total_executions": 0,
                "completed": 0,
                "failed": 0,
                "in_progress": 0,
                "total_tokens": 0,
                "total_artifacts": 0,
            },
            "employees": [],
            "timeline": [],
            "has_activity": False,
        }

    employee_map: dict[str, dict] = {}
    timeline: list[dict] = []
    total_tokens = 0
    total_artifacts = 0
    status_counts = {"completed": 0, "failed": 0, "running": 0, "pending": 0, "cancelled": 0}

    for ex in executions:
        eid = ex["employee_id"]
        status = ex.get("status", "unknown")
        tokens = ex.get("tokens_used", 0) or 0
        total_tokens += tokens
        status_counts[status] = status_counts.get(status, 0) + 1

        if eid not in employee_map:
            employee_map[eid] = {
                "employee_id": eid,
                "employee_name": ex.get("employee_name", "Unknown"),
                "employee_role": ex.get("employee_role", "unknown"),
                "employee_avatar": ex.get("employee_avatar"),
                "executions": [],
                "total_tokens": 0,
                "completed": 0,
                "failed": 0,
                "artifacts_count": 0,
            }

        artifacts = await list_execution_artifacts(ex["id"])
        total_artifacts += len(artifacts)
        employee_map[eid]["artifacts_count"] += len(artifacts)

        progress = _parse_json(ex.get("progress"))
        phase_costs = progress.get("phase_costs", {}) if progress else {}

        phases_completed = []
        logs = await get_execution_logs(ex["id"], limit=50)
        seen_states = set()
        for log in logs:
            s = log.get("state", "")
            if s and s not in seen_states:
                seen_states.add(s)
                phases_completed.append(s)

        sentinel_result = None
        if progress and "sentinel" in str(progress).lower():
            sentinel_result = progress.get("sentinel_verdict") or progress.get("sentinel")

        exec_summary = {
            "execution_id": ex["id"],
            "goal": ex.get("goal", ""),
            "status": status,
            "state": ex.get("state", ""),
            "iteration": ex.get("iteration", 0),
            "tokens_used": tokens,
            "phase_costs": phase_costs,
            "phases_completed": phases_completed,
            "artifacts": [
                {
                    "id": a["id"],
                    "type": a.get("type", ""),
                    "title": a.get("title", ""),
                    "path": a.get("path"),
                    "language": a.get("language"),
                }
                for a in artifacts
            ],
            "sentinel_result": sentinel_result,
            "error": ex.get("error"),
            "created_at": ex.get("created_at", ""),
            "started_at": ex.get("started_at"),
            "completed_at": ex.get("completed_at"),
            "duration_seconds": _calc_duration(ex.get("started_at"), ex.get("completed_at")),
        }

        employee_map[eid]["executions"].append(exec_summary)
        employee_map[eid]["total_tokens"] += tokens
        if status == "completed":
            employee_map[eid]["completed"] += 1
        elif status == "failed":
            employee_map[eid]["failed"] += 1

        timeline.append({
            "timestamp": ex.get("completed_at") or ex.get("started_at") or ex.get("created_at", ""),
            "employee_name": ex.get("employee_name", "Unknown"),
            "employee_role": ex.get("employee_role", ""),
            "event": _timeline_event(status, ex.get("goal", "")),
            "status": status,
            "execution_id": ex["id"],
        })

    employees = sorted(employee_map.values(), key=lambda e: e["total_tokens"], reverse=True)
    timeline.sort(key=lambda t: t["timestamp"])

    return {
        "period": {"since": cutoff, "hours": hours},
        "summary": {
            "total_executions": len(executions),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "in_progress": status_counts.get("running", 0) + status_counts.get("pending", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "total_tokens": total_tokens,
            "total_artifacts": total_artifacts,
            "active_employees": len(employee_map),
        },
        "employees": employees,
        "timeline": timeline,
        "has_activity": True,
    }


async def get_last_seen(user_id: str) -> str | None:
    """Get when the user last marked activity as seen."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT MAX(created_at) as last_seen FROM activity_log
               WHERE user_id = ? AND seen = 1""",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["last_seen"] if row and row["last_seen"] else None
    finally:
        await db.close()


def _parse_json(val: Any) -> dict | None:
    if not val:
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _calc_duration(started: str | None, completed: str | None) -> int | None:
    if not started or not completed:
        return None
    try:
        s = datetime.fromisoformat(started.replace("Z", "+00:00"))
        c = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        return max(0, int((c - s).total_seconds()))
    except (ValueError, TypeError):
        return None


def _timeline_event(status: str, goal: str) -> str:
    goal_short = goal[:80] + ("..." if len(goal) > 80 else "")
    if status == "completed":
        return f"Completed: {goal_short}"
    elif status == "failed":
        return f"Failed: {goal_short}"
    elif status == "running":
        return f"Working on: {goal_short}"
    elif status == "cancelled":
        return f"Cancelled: {goal_short}"
    return f"Started: {goal_short}"
