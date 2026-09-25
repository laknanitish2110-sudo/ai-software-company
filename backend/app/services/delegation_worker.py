"""
Production-grade async delegation worker for persistent AI employees.

Features:
- Concurrent task processing (up to 3 tasks in parallel)
- Redis claim with heartbeat renewal (prevents claim expiry on long tasks)
- Per-task wall-clock timeout (5 minutes)
- Retry with exponential backoff (max 3 attempts)
- Dead-letter marking for permanently failed tasks
- Stale task recovery (sweeps stuck "running" delegation tasks)
- Worker identity tracking
- Graceful shutdown with in-flight task drain
"""

import json
import asyncio
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Task] = None
_shutdown_event: Optional[asyncio.Event] = None
_worker_id: str = ""

CLAIM_TTL = 300
HEARTBEAT_INTERVAL = 60
TASK_TIMEOUT = 300
MAX_RETRIES = 3
MAX_CONCURRENT = 3
STALE_RUNNING_SECONDS = 360


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

        from app.core.database import log_activity
        await log_activity(
            user_id=user_id,
            event_type="delegation_completed",
            title=f"{target['name']} completed a task from {from_name}",
            employee_id=to_emp_id,
            employee_name=target["name"],
            detail=response_text[:300] if response_text else None,
            metadata={"task_id": task_id, "from_employee": from_name, "to_employee": target["name"]},
        )

        logger.info(f"Delegation {task_id}: {from_name} → {target['name']} completed ({_worker_id[:8]})")

        try:
            await _notify_goal_engine(task_id, response_text, user_id, success=True)
        except Exception as ge:
            logger.debug(f"Goal engine notification: {ge}")

        return {"success": True, "result": response_text}

    except Exception as e:
        logger.error(f"Delegation {task_id} failed: {e}")
        await update_employee(to_emp_id, user_id, {"status": "idle"})
        await update_delegation_task(task_id, {"status": "failed", "result": str(e)})

        try:
            await _notify_goal_engine(task_id, str(e), user_id, success=False)
        except Exception:
            pass

        return {"success": False, "error": str(e)}


async def _notify_goal_engine(delegation_task_id: str, result: str, user_id: str, success: bool):
    """Check if this delegation task is linked to a goal task, and notify the goal engine."""
    from app.core.database import get_db
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM goal_tasks WHERE execution_id = ?", (delegation_task_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        return

    from app.services.goal_engine import on_task_completed, on_task_failed
    if success:
        await on_task_completed(row["id"], result, user_id)
    else:
        await on_task_failed(row["id"], result, user_id)


async def _try_claim_task(task_id: str) -> bool:
    """Atomically claim a task using Redis SETNX. Returns True if this worker won the claim."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return True
        claimed = await client.set(
            f"delegation:claim:{task_id}", _worker_id, nx=True, ex=CLAIM_TTL
        )
        return bool(claimed)
    except Exception:
        return True


async def _renew_claim(task_id: str) -> bool:
    """Renew the claim TTL for a running task. Returns False if claim was lost."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return True
        current = await client.get(f"delegation:claim:{task_id}")
        if current and current.decode() == _worker_id:
            await client.expire(f"delegation:claim:{task_id}", CLAIM_TTL)
            return True
        return False
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


async def _run_task_with_timeout(task: dict) -> dict:
    """Run a delegation task with wall-clock timeout and heartbeat renewal."""
    task_id = task["id"]
    heartbeat_active = True

    async def heartbeat_loop():
        while heartbeat_active:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if not heartbeat_active:
                break
            if not await _renew_claim(task_id):
                logger.warning(f"Delegation {task_id}: lost claim during heartbeat")
                break

    hb_task = asyncio.create_task(heartbeat_loop())
    try:
        result = await asyncio.wait_for(
            process_delegation_task(task),
            timeout=TASK_TIMEOUT,
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Delegation {task_id}: timed out after {TASK_TIMEOUT}s")
        from app.core.database import update_delegation_task
        await update_delegation_task(task_id, {
            "status": "failed",
            "result": f"Task timed out after {TASK_TIMEOUT}s",
        })
        return {"success": False, "error": "timeout"}
    finally:
        heartbeat_active = False
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass


async def _get_retry_count(task_id: str) -> int:
    """Get the retry count for a task from Redis."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return 0
        val = await client.get(f"delegation:retries:{task_id}")
        return int(val) if val else 0
    except Exception:
        return 0


async def _increment_retry(task_id: str) -> int:
    """Increment and return the retry count."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return 1
        count = await client.incr(f"delegation:retries:{task_id}")
        await client.expire(f"delegation:retries:{task_id}", 86400)
        return int(count)
    except Exception:
        return 1


async def _mark_dead_letter(task: dict, reason: str):
    """Mark a task as dead-letter after exhausting retries."""
    from app.core.database import update_delegation_task
    task_id = task["id"]
    await update_delegation_task(task_id, {
        "status": "failed",
        "result": f"[DEAD LETTER] {reason} (after {MAX_RETRIES} attempts)",
    })
    logger.error(f"Delegation {task_id}: moved to dead letter — {reason}")


async def _process_with_retry(task: dict):
    """Process a task with retry logic. Moves to dead-letter after MAX_RETRIES failures."""
    task_id = task["id"]
    retries = await _get_retry_count(task_id)

    if retries >= MAX_RETRIES:
        await _mark_dead_letter(task, f"Exceeded max retries ({MAX_RETRIES})")
        return

    result = await _run_task_with_timeout(task)

    if not result.get("success"):
        attempt = await _increment_retry(task_id)
        if attempt >= MAX_RETRIES:
            await _mark_dead_letter(task, result.get("error", "unknown error"))
        else:
            from app.core.database import update_delegation_task
            await update_delegation_task(task_id, {"status": "pending"})
            backoff = min(2 ** attempt * 5, 60)
            logger.info(f"Delegation {task_id}: retry {attempt}/{MAX_RETRIES} in {backoff}s")
            await asyncio.sleep(backoff)


async def _recover_stale_delegations():
    """Sweep delegation tasks stuck in 'running' state and reset them for retry."""
    from app.core.database import recover_stale_delegation_tasks
    try:
        recovered = await recover_stale_delegation_tasks(STALE_RUNNING_SECONDS)
        for task_id in recovered:
            logger.warning(f"Delegation recovery: reset stale task {task_id} to pending")
    except Exception as e:
        logger.debug(f"Delegation stale sweep error: {e}")


async def _worker_loop():
    """Background loop that polls for pending delegation tasks and processes them concurrently."""
    global _worker_id
    _worker_id = f"dlg-{uuid.uuid4().hex[:12]}"
    logger.info(f"Delegation worker started (id={_worker_id}, max_concurrent={MAX_CONCURRENT})")

    sweep_counter = 0
    active_tasks: set[asyncio.Task] = set()

    while not _shutdown_event or not _shutdown_event.is_set():
        try:
            sweep_counter += 1
            if sweep_counter % 30 == 0:
                await _recover_stale_delegations()

            available_slots = MAX_CONCURRENT - len(active_tasks)
            if available_slots <= 0:
                done = {t for t in active_tasks if t.done()}
                active_tasks -= done
                for t in done:
                    try:
                        t.result()
                    except Exception as e:
                        logger.error(f"Delegation task error: {e}")
                await asyncio.sleep(1)
                continue

            from app.core.database import get_pending_delegation_tasks
            tasks = await get_pending_delegation_tasks(limit=available_slots)

            for task in tasks:
                if not await _try_claim_task(task["id"]):
                    continue

                async def _run_and_release(t: dict):
                    try:
                        await _process_with_retry(t)
                    except Exception as e:
                        logger.error(f"Worker error on task {t['id']}: {e}")
                    finally:
                        await _release_claim(t["id"])

                at = asyncio.create_task(_run_and_release(task))
                active_tasks.add(at)

        except Exception as e:
            logger.warning(f"Delegation worker poll error: {e}")

        await asyncio.sleep(2)

    if active_tasks:
        logger.info(f"Delegation worker draining {len(active_tasks)} in-flight tasks...")
        done, pending = await asyncio.wait(active_tasks, timeout=30)
        for t in pending:
            t.cancel()
        logger.info("Delegation worker drained")


def start_delegation_worker():
    """Start the background delegation worker. Safe to call multiple times."""
    global _worker_task, _shutdown_event
    if _worker_task and not _worker_task.done():
        return
    _shutdown_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Delegation worker task created")


def stop_delegation_worker():
    """Stop the background delegation worker with graceful drain."""
    global _worker_task, _shutdown_event
    if _shutdown_event:
        _shutdown_event.set()
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None
