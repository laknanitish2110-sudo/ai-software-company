"""
Background Worker & ARQ Distributed Worker Service (P4.5 / P4.7-C)

Executes durable queued jobs outside the HTTP request thread lifecycle.
Maintains periodic heartbeat ticks and manages execution completion/failure state transitions.

Supports dual worker engines via TASK_WORKER_ENGINE:
- "in_process": Single-node background worker (BackgroundWorker)
- "arq": Distributed Redis worker fleet (WorkerSettings + run_autonomous_pipeline_job)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable, Awaitable

from app.core.config import REDIS_URL, TASK_WORKER_ENGINE
from app.services.task_queue import task_queue, STATUS_RUNNING, STATUS_QUEUED, ExecutionCancelledError
from app.services.redis_coordinator import redis_coordinator

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """
    Single-node background worker for claiming and executing queued tasks (In-Process Engine).
    """
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
        self._running = False
        self._active_heartbeats: Dict[str, asyncio.Task] = {}

    async def _heartbeat_loop(self, execution_id: str, interval_seconds: int = 5):
        try:
            while self._running:
                await task_queue.heartbeat(execution_id)
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Heartbeat loop error for execution {execution_id}: {e}")

    async def execute_job(self, execution: Dict[str, Any], pipeline_fn: Callable[[str], Awaitable[None]]):
        execution_id = execution["id"]
        project_id = execution["project_id"]
        
        self._running = True
        hb_task = asyncio.create_task(self._heartbeat_loop(execution_id, interval_seconds=5))
        self._active_heartbeats[execution_id] = hb_task

        try:
            logger.info(f"Worker {self.worker_id} executing job {execution_id} for project {project_id}")
            await pipeline_fn(project_id)
            await task_queue.complete(execution_id)
            logger.info(f"Worker {self.worker_id} completed job {execution_id} for project {project_id}")
        except Exception as e:
            logger.error(f"Worker {self.worker_id} job {execution_id} failed: {e}")
            await task_queue.fail(execution_id, str(e))
        finally:
            self._running = False
            hb_task.cancel()
            self._active_heartbeats.pop(execution_id, None)


# Global in-process worker instance
background_worker = BackgroundWorker()


# ==============================================================================
# ARQ DISTRIBUTED WORKER ENGINE (P4.7-C)
# ==============================================================================

async def run_autonomous_pipeline_job(ctx: dict, execution_id: str, project_id: str, user_id: str):
    """
    ARQ Worker Job Handler (P4.7-C).
    1. Validates execution state & claims atomically in PostgreSQL database.
       If status != 'QUEUED', this job is a duplicate -> Worker safely exits (no-op).
    2. Registers project execution in orchestrator (acquires Redis lock).
       If lock acquisition fails (None returned), another worker owns project -> Worker safely exits (no-op).
    3. Runs pipeline via orchestrator.start_project(problem_statement, user_id).
    4. Maintains PostgreSQL heartbeat & Redis LockHeartbeat.
    5. Updates executions table status to COMPLETED or FAILED upon completion.
    """
    from app.services.orchestrator import orchestrator
    from app.core.database import get_db, get_project_for_user

    worker_id = ctx.get("worker_id", f"arq_worker_{uuid.uuid4().hex[:8]}")

    # Step 1: Verify PostgreSQL ownership & claim execution atomically
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM executions WHERE id = ? AND user_id = ?",
            (execution_id, user_id)
        )
        row = await cursor.fetchone()
        if not row or row["status"] != STATUS_QUEUED:
            logger.info(f"ARQ Worker {worker_id}: execution {execution_id} is not QUEUED or ownership mismatch. Duplicate no-op exit.")
            return

        # Atomic claim query
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """
            UPDATE executions 
            SET status = ?, worker_id = ?, started_at = ?, last_heartbeat = ?
            WHERE id = ? AND status = ?
            """,
            (STATUS_RUNNING, worker_id, now_iso, now_iso, execution_id, STATUS_QUEUED)
        )
        await db.commit()

        claimed = await task_queue.get_execution(execution_id)
        if not claimed or claimed["status"] != STATUS_RUNNING or claimed.get("worker_id") != worker_id:
            logger.info(f"ARQ Worker {worker_id}: execution {execution_id} already claimed. Duplicate no-op exit.")
            return
    finally:
        await db.close()

    # Step 2: Fetch project details
    proj = await get_project_for_user(project_id, user_id)
    if not proj:
        await task_queue.fail(execution_id, f"Project {project_id} not found or user unauthorized")
        return

    # Step 3: Run pipeline via orchestrator with heartbeats
    stop_hb = False

    async def _db_hb_loop():
        try:
            while not stop_hb:
                await task_queue.heartbeat(execution_id)
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    hb_task = asyncio.create_task(_db_hb_loop())

    try:
        await orchestrator.start_project(
            problem_statement=proj["problem_statement"],
            user_id=user_id,
            auto_approve=proj.get("auto_approve", True),
            execution_id=execution_id
        )
        # Await pipeline task if running async
        if project_id in orchestrator._running_tasks:
            t = orchestrator._running_tasks[project_id]
            if not t.done():
                await t

        if redis_coordinator.is_cancelled(execution_id):
            raise ExecutionCancelledError(f"Cancellation requested for execution {execution_id}")

        await task_queue.complete(execution_id)
    except ExecutionCancelledError as e:
        logger.info(f"ARQ Worker {worker_id} job {execution_id} cancelled cleanly: {e}")
        await task_queue.cancel(execution_id)
        await redis_coordinator.publish_event(project_id, "cancellation_completed", {"execution_id": execution_id})
    except Exception as e:
        logger.error(f"ARQ Worker {worker_id} job {execution_id} failed: {e}")
        await task_queue.fail(execution_id, str(e))
    finally:
        stop_hb = True
        if hb_task and not hb_task.done():
            hb_task.cancel()


try:
    from arq.connections import RedisSettings

    class WorkerSettings:
        functions = [run_autonomous_pipeline_job]
        redis_settings = RedisSettings.from_dsn(REDIS_URL) if REDIS_URL else None
        queue_name = "arq:queue"
        max_jobs = 4
        job_timeout = 600
        keep_result = 3600
        max_retries = 0  # ARQ retries MUST NOT multiply business repair attempts
        health_check_interval = 10
except ImportError:
    WorkerSettings = None  # Fallback if arq is not loaded
