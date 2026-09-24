"""
Async delegation worker for persistent AI employees.

Processes delegation tasks from the queue in the background:
1. Picks up pending tasks from delegation_tasks table
2. Runs the target employee's LLM with their tools/memory
3. Stores result and publishes completion event via Redis
4. Originating employee can poll for results via check_delegation tool

Uses Redis pub/sub for real-time notifications and the database as
the durable task queue (no tasks lost on restart).
"""

import json
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Task] = None


async def process_delegation_task(task: dict) -> dict:
    """Execute a single delegation task — run the target employee on the delegated work."""
    from app.core.database import (
        get_employee, update_delegation_task, get_or_create_active_session,
        add_session_message, get_session_messages, update_employee,
        retrieve_memories_for_context, list_templates,
    )
    from app.services.tool_executor import (
        get_tools_for_employee, EMPLOYEE_ROLE_TO_ENGINE_ROLE, execute_tool,
    )
    from app.agents.engine import call_llm_with_fallback
    from app.services.memory_engine import schedule_memory_extraction

    task_id = task["id"]
    user_id = task["user_id"]
    to_emp_id = task["to_employee_id"]
    from_emp_id = task["from_employee_id"]
    project_id = task.get("project_id")

    await update_delegation_task(task_id, {"status": "running"})

    target = await get_employee(to_emp_id, user_id)
    if not target:
        await update_delegation_task(task_id, {"status": "failed", "result": "Target employee not found"})
        return {"success": False, "error": "Target employee not found"}

    from_emp = await get_employee(from_emp_id, user_id)
    from_name = from_emp["name"] if from_emp else "a teammate"

    if target["status"] in ("archived", "paused"):
        await update_delegation_task(task_id, {"status": "failed", "result": f"{target['name']} is {target['status']}"})
        return {"success": False, "error": f"{target['name']} is {target['status']}"}

    try:
        await update_employee(to_emp_id, user_id, {"status": "thinking"})

        session = await get_or_create_active_session(to_emp_id, project_id)
        await update_delegation_task(task_id, {"session_id": session["id"]})

        delegation_msg = f"[Delegated from {from_name}]\n\n{task['task']}"
        if task.get("context"):
            delegation_msg += f"\n\nContext: {task['context']}"

        await add_session_message(session["id"], "user", delegation_msg)

        memories = await retrieve_memories_for_context(to_emp_id, query=task["task"], limit=5)
        memory_context = ""
        if memories:
            memory_lines = [f"- [{m['type']}] {m['content']}" for m in memories]
            memory_context = "\n\nYour memories:\n" + "\n".join(memory_lines)

        system_prompt = f"You are {target['name']}, a {target['role']}."
        if target.get("persona"):
            system_prompt += f"\n\n{target['persona']}"
        if memory_context:
            system_prompt += memory_context
        system_prompt += f"\n\nA teammate ({from_name}) has delegated a task to you. Complete it thoroughly."

        history = await get_session_messages(session["id"], limit=10)
        chat_messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            if msg["role"] == "user":
                chat_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "employee":
                chat_messages.append({"role": "assistant", "content": msg["content"]})

        tgt_config = target.get("config") or {}
        target_tools_names = tgt_config.get("default_tools") if isinstance(tgt_config, dict) else None
        if not target_tools_names and target.get("template_id"):
            templates = await list_templates(active_only=True)
            tmpl = next((t for t in templates if t["id"] == target["template_id"]), None)
            if tmpl:
                target_tools_names = tmpl.get("default_tools")

        target_tools = get_tools_for_employee(target_tools_names)
        no_delegate_tools = [t for t in target_tools if t["function"]["name"] != "delegate"]

        engine_role = EMPLOYEE_ROLE_TO_ENGINE_ROLE.get(target["role"].lower(), "ceo")

        max_iterations = 3
        response_text = ""

        for iteration in range(max_iterations):
            text, tool_calls = await call_llm_with_fallback(
                messages=chat_messages,
                role=engine_role,
                temperature=0.7,
                tools=no_delegate_tools if no_delegate_tools else None,
            )

            if not tool_calls:
                response_text = text
                break

            tc_msg = {"role": "assistant", "content": None, "tool_calls": tool_calls}
            chat_messages.append(tc_msg)
            await add_session_message(session["id"], "tool_calls", json.dumps(tool_calls))
            await update_employee(to_emp_id, user_id, {"status": "tool_execution"})

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    func_args = {}

                result = await execute_tool(
                    tool_name=func_name,
                    arguments=func_args,
                    employee_id=to_emp_id,
                    user_id=user_id,
                    project_id=project_id,
                )
                result_str = json.dumps(result)
                if len(result_str) > 4000:
                    result_str = result_str[:4000] + "...(truncated)"

                chat_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})
                await add_session_message(
                    session["id"], "tool_result",
                    json.dumps({"tool_call_id": tc["id"], "tool": func_name, "result": result_str}),
                )

            await update_employee(to_emp_id, user_id, {"status": "thinking"})
        else:
            response_text = text or "Task completed."

        await add_session_message(session["id"], "employee", response_text)
        await update_employee(to_emp_id, user_id, {"status": "idle"})

        schedule_memory_extraction(to_emp_id, delegation_msg, response_text, session["id"])

        from app.core.database import now_iso
        await update_delegation_task(task_id, {
            "status": "completed",
            "result": response_text,
            "session_id": session["id"],
            "completed_at": now_iso(),
        })

        from app.services.redis_coordinator import redis_coordinator
        try:
            await redis_coordinator.publish_event(
                project_id or f"delegation:{from_emp_id}",
                "delegation_completed",
                {
                    "task_id": task_id,
                    "from_employee": from_name,
                    "to_employee": target["name"],
                    "result_preview": response_text[:200],
                },
            )
        except Exception as pub_err:
            logger.debug(f"Redis publish notice for delegation: {pub_err}")

        logger.info(f"Delegation {task_id}: {from_name} → {target['name']} completed")
        return {"success": True, "result": response_text}

    except Exception as e:
        logger.error(f"Delegation {task_id} failed: {e}")
        await update_employee(to_emp_id, user_id, {"status": "idle"})
        await update_delegation_task(task_id, {"status": "failed", "result": str(e)})
        return {"success": False, "error": str(e)}


async def _try_claim_task(task_id: str) -> bool:
    """Atomically claim a task using Redis SETNX. Returns True if this worker won the claim."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return True
        claimed = await client.set(
            f"delegation:claim:{task_id}", "1", nx=True, ex=300
        )
        return bool(claimed)
    except Exception:
        return True


async def _release_claim(task_id: str):
    """Release a task claim after completion or failure."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client:
            await client.delete(f"delegation:claim:{task_id}")
    except Exception:
        pass


async def _worker_loop():
    """Background loop that polls for pending delegation tasks and processes them."""
    logger.info("Delegation worker started")
    while True:
        try:
            from app.core.database import get_pending_delegation_tasks
            tasks = await get_pending_delegation_tasks(limit=5)
            for task in tasks:
                if not await _try_claim_task(task["id"]):
                    continue
                try:
                    await process_delegation_task(task)
                except Exception as e:
                    logger.error(f"Worker error on task {task['id']}: {e}")
                finally:
                    await _release_claim(task["id"])
        except Exception as e:
            logger.warning(f"Delegation worker poll error: {e}")

        await asyncio.sleep(2)


def start_delegation_worker():
    """Start the background delegation worker. Safe to call multiple times."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Delegation worker task created")


def stop_delegation_worker():
    """Stop the background delegation worker."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None
