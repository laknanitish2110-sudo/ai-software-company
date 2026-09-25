"""Background task scheduler for employee scheduled work.

Computes next run times from cron expressions and provides a polling-based
runner that can be kicked off from the FastAPI lifespan or a background thread.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def parse_cron_field(field: str, min_val: int, max_val: int) -> list[int]:
    if field == "*":
        return list(range(min_val, max_val + 1))
    values = set()
    for part in field.split(","):
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            start = min_val if base == "*" else int(base)
            values.update(range(start, max_val + 1, step))
        elif "-" in part:
            lo, hi = part.split("-", 1)
            values.update(range(int(lo), int(hi) + 1))
        else:
            values.add(int(part))
    return sorted(v for v in values if min_val <= v <= max_val)


def compute_next_run(cron_expr: str, after: datetime | None = None) -> str | None:
    """Compute the next run time from a 5-field cron expression (min hour dom month dow).
    Returns ISO string or None if parsing fails."""
    if not cron_expr or not cron_expr.strip():
        return None
    try:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return None
        minutes = parse_cron_field(parts[0], 0, 59)
        hours = parse_cron_field(parts[1], 0, 23)
        doms = parse_cron_field(parts[2], 1, 31)
        months = parse_cron_field(parts[3], 1, 12)
        dows = parse_cron_field(parts[4], 0, 6)

        now = after or datetime.now(timezone.utc)
        candidate = now + timedelta(minutes=1)
        candidate = candidate.replace(second=0, microsecond=0)

        for _ in range(525600):  # max 1 year of minutes
            if (candidate.month in months and
                candidate.day in doms and
                candidate.weekday() in [d % 7 for d in dows] and
                candidate.hour in hours and
                candidate.minute in minutes):
                return candidate.isoformat()
            candidate += timedelta(minutes=1)
        return None
    except Exception as e:
        logger.warning(f"Failed to parse cron expression '{cron_expr}': {e}")
        return None


async def run_scheduled_task(task: dict) -> dict:
    """Execute a scheduled task by creating a session and sending the prompt through the LLM."""
    from app.core.database import (
        create_session, add_session_message, update_scheduled_task,
        get_employee, log_activity, now_iso, update_employee,
        retrieve_memories_for_context,
    )

    employee_id = task["employee_id"]
    user_id = task["user_id"]
    task_id = task["id"]
    prompt = task["task_prompt"]

    logger.info(f"Running scheduled task '{task['name']}' for employee {employee_id}")

    try:
        employee = await get_employee(employee_id)
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")

        session = await create_session(employee_id, user_id)
        session_id = session["id"]

        await add_session_message(session_id, "user", f"[Scheduled Task: {task['name']}]\n\n{prompt}")
        await update_employee(employee_id, user_id, {"status": "thinking"})

        memories = await retrieve_memories_for_context(employee_id, query=prompt, limit=10)
        memory_context = ""
        if memories:
            memory_lines = [f"- [{m['type']}] {m['content']}" for m in memories]
            memory_context = "\n\nYour memories:\n" + "\n".join(memory_lines)

        system_prompt = f"You are {employee['name']}, a {employee['role']}."
        if employee.get("persona"):
            system_prompt += f"\n\n{employee['persona']}"
        if memory_context:
            system_prompt += memory_context
        system_prompt += "\n\nThis is a scheduled background task. Complete it thoroughly and report your results."

        chat_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        from app.agents.engine import call_llm_with_fallback
        text, _ = await call_llm_with_fallback(
            messages=chat_messages, role="ceo", temperature=0.7,
        )

        response_text = text or "Task completed."
        await add_session_message(session_id, "employee", response_text)
        await update_employee(employee_id, user_id, {"status": "idle"})

        run_count = (task.get("run_count") or 0) + 1
        update_data = {
            "last_run_at": now_iso(),
            "last_run_status": "success",
            "last_run_result": response_text[:2000],
            "run_count": run_count,
        }

        if task["schedule_type"] == "recurring" and task.get("cron_expression"):
            update_data["next_run_at"] = compute_next_run(task["cron_expression"])
        else:
            update_data["is_active"] = 0
            update_data["next_run_at"] = None

        await update_scheduled_task(task_id, update_data)
        await log_activity(
            user_id=user_id,
            event_type="scheduled_task_completed",
            title=f"Scheduled task completed: {task['name']}",
            employee_id=employee_id,
            employee_name=employee.get("name"),
            detail=f"Task ran successfully (run #{run_count})",
        )
        return {"status": "success", "session_id": session_id}

    except Exception as e:
        logger.error(f"Scheduled task {task_id} failed: {e}")
        try:
            await update_employee(employee_id, user_id, {"status": "idle"})
        except Exception:
            pass
        await update_scheduled_task(task_id, {
            "last_run_at": now_iso(),
            "last_run_status": "error",
            "last_run_result": str(e)[:2000],
            "run_count": (task.get("run_count") or 0) + 1,
        })
        return {"status": "error", "error": str(e)}


async def scheduler_loop(interval: int = 60):
    """Background loop that polls for due tasks and runs them."""
    from app.core.database import get_due_scheduled_tasks
    logger.info("Scheduler loop started")
    while True:
        try:
            due = await get_due_scheduled_tasks(limit=5)
            for task in due:
                try:
                    await run_scheduled_task(task)
                except Exception as e:
                    logger.error(f"Failed to run task {task.get('id')}: {e}")
        except Exception as e:
            logger.error(f"Scheduler poll error: {e}")
        await asyncio.sleep(interval)
