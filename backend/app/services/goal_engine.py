"""
Goal Engine — decomposes high-level goals into executable task graphs,
assigns tasks to employees, orchestrates execution, and tracks progress.
"""

import json
import asyncio
import logging
from typing import Optional

from app.core.database import (
    list_employees, create_goal_task, update_goal, update_goal_task,
    list_goal_tasks, get_goal, get_next_runnable_goal_tasks,
    get_goal_progress, create_delegation_task, now_iso, log_activity,
)
from app.agents.engine import call_llm_with_fallback

logger = logging.getLogger(__name__)


DECOMPOSE_PROMPT = """You are a project planning AI. Given a goal, break it into concrete tasks that employees can execute.

Available employees:
{employees}

Goal: {title}
{description}

Produce a JSON array of tasks. Each task has:
- "title": short action-oriented title (e.g., "Research competitor pricing")
- "description": 1-2 sentence description of what to do
- "assigned_role": the role of the employee best suited (e.g., "researcher", "engineer", "designer")
- "depends_on_indices": array of 0-based indices of tasks this depends on (empty if none)
- "execution_type": "delegation" (delegate to employee) or "autonomous" (employee works independently)

Rules:
- Keep tasks between 3-8 items. Each should be completable in one session.
- Order tasks logically. Earlier tasks should feed into later ones.
- Assign roles that match employee capabilities.
- Use "autonomous" for complex multi-step tasks, "delegation" for simpler ones.
- Return ONLY the JSON array, no markdown or explanation.
"""


async def decompose_goal(goal_id: str, user_id: str) -> dict:
    """Use LLM to decompose a goal into a task graph and save it."""
    goal = await get_goal(goal_id, user_id)
    if not goal:
        return {"error": "Goal not found"}

    employees = await list_employees(user_id)
    if not employees:
        return {"error": "No employees available"}

    emp_descriptions = []
    for e in employees:
        if e["status"] == "archived":
            continue
        emp_descriptions.append(f"- {e['name']} (role: {e['role']}, id: {e['id']})")
    emp_text = "\n".join(emp_descriptions) if emp_descriptions else "No active employees"

    desc_text = f"Description: {goal['description']}" if goal.get("description") else ""

    prompt = DECOMPOSE_PROMPT.format(
        employees=emp_text, title=goal["title"], description=desc_text,
    )

    messages = [
        {"role": "system", "content": "You are a project planning assistant. Return only valid JSON."},
        {"role": "user", "content": prompt},
    ]

    response = await call_llm_with_fallback(messages=messages, role="ceo", temperature=0.3)
    if isinstance(response, tuple):
        response = response[0]

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        tasks_data = json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"Goal decomposition failed to parse: {response[:200]}")
        return {"error": "Failed to parse task plan from LLM"}

    if not isinstance(tasks_data, list) or len(tasks_data) == 0:
        return {"error": "LLM returned empty task list"}

    role_to_employee = {}
    for e in employees:
        if e["status"] != "archived":
            role_to_employee[e["role"].lower()] = e

    created_tasks = []
    task_id_map = {}

    for idx, td in enumerate(tasks_data):
        role = td.get("assigned_role", "").lower()
        emp = role_to_employee.get(role)
        if not emp:
            emp = employees[0] if employees else None

        dep_indices = td.get("depends_on_indices", [])
        dep_ids = [task_id_map[i] for i in dep_indices if i in task_id_map]

        task = await create_goal_task(
            goal_id=goal_id,
            title=td.get("title", f"Task {idx + 1}"),
            description=td.get("description"),
            assigned_employee_id=emp["id"] if emp else None,
            depends_on=dep_ids if dep_ids else None,
            execution_type=td.get("execution_type", "delegation"),
            sort_order=idx,
        )
        created_tasks.append(task)
        task_id_map[idx] = task["id"]

    await update_goal(goal_id, user_id, {
        "status": "planned",
        "plan": json.dumps(tasks_data),
        "total_tasks": len(created_tasks),
    })

    return {"goal_id": goal_id, "tasks": created_tasks}


async def start_goal(goal_id: str, user_id: str) -> dict:
    """Start executing a planned goal — kicks off the first runnable tasks."""
    goal = await get_goal(goal_id, user_id)
    if not goal:
        return {"error": "Goal not found"}
    if goal["status"] not in ("planned", "paused"):
        return {"error": f"Cannot start goal in '{goal['status']}' status"}

    await update_goal(goal_id, user_id, {
        "status": "running", "started_at": now_iso(),
    })

    launched = await _launch_runnable_tasks(goal_id, user_id)

    await log_activity(
        user_id=user_id, event_type="goal_started",
        title=f"Goal started: {goal['title']}",
        detail=f"Launched {len(launched)} initial tasks",
        metadata={"goal_id": goal_id},
    )

    return {"goal_id": goal_id, "launched": len(launched)}


async def _launch_runnable_tasks(goal_id: str, user_id: str) -> list[str]:
    """Find and launch all tasks whose dependencies are met."""
    runnable = await get_next_runnable_goal_tasks(goal_id)
    launched = []

    goal = await get_goal(goal_id, user_id)
    owner_id = goal.get("owner_employee_id") if goal else None

    for task in runnable:
        emp_id = task.get("assigned_employee_id")
        if not emp_id:
            continue

        await update_goal_task(task["id"], {"status": "running", "started_at": now_iso()})

        from_emp_id = owner_id or emp_id

        delegation = await create_delegation_task(
            from_employee_id=from_emp_id,
            to_employee_id=emp_id,
            user_id=user_id,
            task=task["title"],
            context=task.get("description"),
        )

        await update_goal_task(task["id"], {"execution_id": delegation["id"]})
        launched.append(task["id"])

    return launched


async def on_task_completed(goal_task_id: str, result: str, user_id: str):
    """Called when a goal task finishes — updates progress and launches next tasks."""
    from app.core.database import get_goal_progress

    # Find which goal this task belongs to
    from app.core.database import get_db
    db = await get_db()
    try:
        cursor = await db.execute("SELECT goal_id FROM goal_tasks WHERE id = ?", (goal_task_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        return

    goal_id = row["goal_id"]
    await update_goal_task(goal_task_id, {
        "status": "completed", "result": result, "completed_at": now_iso(),
    })

    progress = await get_goal_progress(goal_id)
    goal = await get_goal(goal_id, user_id)
    if not goal:
        return

    await update_goal(goal_id, user_id, {
        "progress": progress["progress"],
        "completed_tasks": progress["completed"],
    })

    if progress["completed"] == progress["total"]:
        await update_goal(goal_id, user_id, {
            "status": "completed", "completed_at": now_iso(),
            "result": f"All {progress['total']} tasks completed successfully.",
        })
        await log_activity(
            user_id=user_id, event_type="goal_completed",
            title=f"Goal completed: {goal['title']}",
            detail=f"All {progress['total']} tasks finished",
            metadata={"goal_id": goal_id},
        )
    else:
        await _launch_runnable_tasks(goal_id, user_id)


async def on_task_failed(goal_task_id: str, error: str, user_id: str):
    """Called when a goal task fails."""
    from app.core.database import get_db
    db = await get_db()
    try:
        cursor = await db.execute("SELECT goal_id FROM goal_tasks WHERE id = ?", (goal_task_id,))
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        return

    goal_id = row["goal_id"]
    await update_goal_task(goal_task_id, {
        "status": "failed", "result": error, "completed_at": now_iso(),
    })

    progress = await get_goal_progress(goal_id)
    goal = await get_goal(goal_id, user_id)
    if not goal:
        return

    await update_goal(goal_id, user_id, {
        "progress": progress["progress"],
        "completed_tasks": progress["completed"],
    })

    all_done = (progress["completed"] + progress["failed"]) == progress["total"]
    if all_done:
        await update_goal(goal_id, user_id, {
            "status": "failed",
            "completed_at": now_iso(),
            "result": f"{progress['failed']} of {progress['total']} tasks failed.",
        })
