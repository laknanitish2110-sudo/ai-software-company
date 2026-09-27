"""
Durable autonomous execution worker.

Mirrors the delegation_worker pattern but adapted for long-running executions:
- Redis SETNX claim + heartbeat renewal (prevents double-execution)
- Lower concurrency (MAX_CONCURRENT=2) — executions are heavier than delegations
- Longer timeout (30 min wall-clock) for complex multi-phase tasks
- State machine checkpointing — survives process restarts
- Retry with exponential backoff + dead-letter queue
- Stale execution recovery sweep
- Goal engine notification on completion/failure
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

CLAIM_TTL = 600
HEARTBEAT_INTERVAL = 120
EXECUTION_TIMEOUT = 1800
MAX_RETRIES = 2
MAX_CONCURRENT = 2
STALE_RUNNING_SECONDS = 1920


async def _process_execution(execution: dict) -> dict:
    """Run a single autonomous execution through the controller."""
    from app.services.execution_controller import AutonomousExecutionController

    execution_id = execution["id"]
    controller = AutonomousExecutionController(execution_id)

    try:
        await controller.run()

        from app.core.database import get_autonomous_execution
        final = await get_autonomous_execution(execution_id)
        status = final["status"] if final else "unknown"

        if status == "completed":
            await _notify_goal_engine(execution, success=True)
            return {"success": True, "execution_id": execution_id}
        else:
            error = final.get("error", "Execution did not complete") if final else "Unknown"
            await _notify_goal_engine(execution, success=False, error=error)
            return {"success": False, "error": error, "execution_id": execution_id}

    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"Execution {execution_id} worker error: {e}", exc_info=True)
        from app.core.database import update_autonomous_execution, now_iso
        await update_autonomous_execution(execution_id, {
            "status": "failed",
            "error": f"Worker error: {e}",
            "completed_at": now_iso(),
        })
        await _notify_goal_engine(execution, success=False, error=str(e))
        return {"success": False, "error": str(e), "execution_id": execution_id}


async def _notify_goal_engine(execution: dict, success: bool, error: str | None = None):
    """Notify goal engine if this execution is linked to a goal task."""
    from app.core.database import get_db
    execution_id = execution["id"]
    user_id = execution.get("user_id", "")

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM goal_tasks WHERE execution_id = ?", (execution_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        return

    try:
        from app.services.goal_engine import on_task_completed, on_task_failed
        if success:
            result = execution.get("result", "Execution completed")
            await on_task_completed(row["id"], result, user_id)
        else:
            await on_task_failed(row["id"], error or "Execution failed", user_id)
    except Exception as e:
        logger.debug(f"Goal engine notification error: {e}")


async def _try_claim(execution_id: str) -> bool:
    """Atomically claim an execution using Redis SETNX."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return True
        claimed = await client.set(
            f"execution:claim:{execution_id}", _worker_id, nx=True, ex=CLAIM_TTL
        )
        return bool(claimed)
    except Exception:
        return True


async def _renew_claim(execution_id: str) -> bool:
    """Renew the claim TTL. Returns False if claim was lost."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return True
        current = await client.get(f"execution:claim:{execution_id}")
        if current and current.decode() == _worker_id:
            await client.expire(f"execution:claim:{execution_id}", CLAIM_TTL)
            return True
        return False
    except Exception:
        return True


async def _release_claim(execution_id: str):
    """Release an execution claim."""
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client:
            await client.delete(f"execution:claim:{execution_id}")
    except Exception:
        pass


async def _run_with_timeout(execution: dict) -> dict:
    """Run an execution with wall-clock timeout and heartbeat renewal."""
    execution_id = execution["id"]
    heartbeat_active = True

    async def heartbeat_loop():
        while heartbeat_active:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if not heartbeat_active:
                break
            if not await _renew_claim(execution_id):
                logger.warning(f"Execution {execution_id}: lost claim during heartbeat")
                break

    hb_task = asyncio.create_task(heartbeat_loop())
    try:
        result = await asyncio.wait_for(
            _process_execution(execution),
            timeout=EXECUTION_TIMEOUT,
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Execution {execution_id}: timed out after {EXECUTION_TIMEOUT}s")
        from app.core.database import update_autonomous_execution, now_iso
        await update_autonomous_execution(execution_id, {
            "status": "failed",
            "error": f"Worker timeout after {EXECUTION_TIMEOUT}s",
            "completed_at": now_iso(),
        })
        return {"success": False, "error": "timeout"}
    finally:
        heartbeat_active = False
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass


async def _get_retry_count(execution_id: str) -> int:
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return 0
        val = await client.get(f"execution:retries:{execution_id}")
        return int(val) if val else 0
    except Exception:
        return 0


async def _increment_retry(execution_id: str) -> int:
    from app.services.redis_coordinator import redis_coordinator
    try:
        client = await redis_coordinator._get_client()
        if client is None:
            return 1
        count = await client.incr(f"execution:retries:{execution_id}")
        await client.expire(f"execution:retries:{execution_id}", 86400)
        return int(count)
    except Exception:
        return 1


async def _mark_dead_letter(execution: dict, reason: str):
    from app.core.database import update_autonomous_execution, now_iso
    execution_id = execution["id"]
    await update_autonomous_execution(execution_id, {
        "status": "failed",
        "error": f"[DEAD LETTER] {reason} (after {MAX_RETRIES} attempts)",
        "completed_at": now_iso(),
    })
    logger.error(f"Execution {execution_id}: moved to dead letter — {reason}")


async def _process_with_retry(execution: dict):
    """Process with retry logic. Moves to dead-letter after MAX_RETRIES."""
    execution_id = execution["id"]
    retries = await _get_retry_count(execution_id)

    if retries >= MAX_RETRIES:
        await _mark_dead_letter(execution, f"Exceeded max retries ({MAX_RETRIES})")
        return

    result = await _run_with_timeout(execution)

    if not result.get("success"):
        attempt = await _increment_retry(execution_id)
        if attempt >= MAX_RETRIES:
            await _mark_dead_letter(execution, result.get("error", "unknown error"))
        else:
            from app.core.database import update_autonomous_execution
            await update_autonomous_execution(execution_id, {"status": "pending"})
            backoff = min(2 ** attempt * 10, 120)
            logger.info(f"Execution {execution_id}: retry {attempt}/{MAX_RETRIES} in {backoff}s")
            await asyncio.sleep(backoff)


async def _get_pending_executions(limit: int = 2) -> list[dict]:
    """Fetch autonomous executions in 'pending' status."""
    from app.core.database import get_db
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM autonomous_executions WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def _recover_stale_executions():
    """Sweep executions stuck in 'running' and reset for retry."""
    from app.core.database import recover_stale_autonomous_executions
    try:
        recovered = await recover_stale_autonomous_executions(STALE_RUNNING_SECONDS)
        for execution_id in recovered:
            logger.warning(f"Execution recovery: reset stale {execution_id} to failed")
    except Exception as e:
        logger.debug(f"Execution stale sweep error: {e}")


async def _worker_loop():
    """Background loop that polls for pending executions and processes them."""
    global _worker_id
    _worker_id = f"exec-{uuid.uuid4().hex[:12]}"
    logger.info(f"Execution worker started (id={_worker_id}, max_concurrent={MAX_CONCURRENT})")

    sweep_counter = 0
    active_tasks: set[asyncio.Task] = set()

    while not _shutdown_event or not _shutdown_event.is_set():
        try:
            sweep_counter += 1
            if sweep_counter % 15 == 0:
                await _recover_stale_executions()

            done = {t for t in active_tasks if t.done()}
            active_tasks -= done
            for t in done:
                try:
                    t.result()
                except Exception as e:
                    logger.error(f"Execution task error: {e}")

            available_slots = MAX_CONCURRENT - len(active_tasks)
            if available_slots <= 0:
                await asyncio.sleep(3)
                continue

            executions = await _get_pending_executions(limit=available_slots)

            for execution in executions:
                if not await _try_claim(execution["id"]):
                    continue

                async def _run_and_release(ex: dict):
                    try:
                        await _process_with_retry(ex)
                    except Exception as e:
                        logger.error(f"Worker error on execution {ex['id']}: {e}")
                    finally:
                        await _release_claim(ex["id"])

                at = asyncio.create_task(_run_and_release(execution))
                active_tasks.add(at)

        except Exception as e:
            logger.warning(f"Execution worker poll error: {e}")

        await asyncio.sleep(3)

    if active_tasks:
        logger.info(f"Execution worker draining {len(active_tasks)} in-flight executions...")
        done, pending = await asyncio.wait(active_tasks, timeout=60)
        for t in pending:
            t.cancel()
        logger.info("Execution worker drained")


def start_execution_worker():
    """Start the background execution worker. Safe to call multiple times."""
    global _worker_task, _shutdown_event
    if _worker_task and not _worker_task.done():
        return
    _shutdown_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Execution worker task created")


def stop_execution_worker():
    """Stop the execution worker with graceful drain."""
    global _worker_task, _shutdown_event
    if _shutdown_event:
        _shutdown_event.set()
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None
