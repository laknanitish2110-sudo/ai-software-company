"""
Provider-Independent Durable Task Queue Service (P4.5 / P4.7-C / P4.7-D)

Stores durable task execution records in PostgreSQL and supports dual worker backends:
- In-process BackgroundWorker (when TASK_WORKER_ENGINE="in_process")
- Distributed ARQ Redis Worker Queue (when TASK_WORKER_ENGINE="arq")
Supports atomic cancellation state transitions: QUEUED/RUNNING -> CANCELLING -> CANCELLED.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.core.database import get_db
from app.core.config import TASK_WORKER_ENGINE, REDIS_URL
from app.models.schemas import ProjectStatus

logger = logging.getLogger(__name__)

# State Machine Constants
STATUS_QUEUED = "QUEUED"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_RECOVERABLE = "RECOVERABLE"
STATUS_CANCELLING = "CANCELLING"
STATUS_CANCELLED = "CANCELLED"

VALID_EXECUTION_STATES = {
    STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED,
    STATUS_FAILED, STATUS_RECOVERABLE, STATUS_CANCELLING, STATUS_CANCELLED
}


class ExecutionCancelledError(Exception):
    """Raised when an active execution is cancelled by user request."""
    pass


class TaskQueue:
    """
    Durable task queue interface backed by PostgreSQL database storage.
    """
    async def enqueue_arq(self, execution_id: str, project_id: str, user_id: str):
        """Enqueues execution job payload into ARQ Redis queue."""
        if not REDIS_URL:
            logger.info("REDIS_URL is unconfigured; skipping ARQ enqueueing.")
            return
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
            redis_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
            await redis_pool.enqueue_job(
                "run_autonomous_pipeline_job",
                execution_id,
                project_id,
                user_id,
                _job_id=execution_id
            )
            await redis_pool.close()
        except Exception as e:
            logger.error(f"Failed to enqueue ARQ job {execution_id}: {e}")

    async def enqueue(self, project_id: str, user_id: str) -> Dict[str, Any]:
        """Enqueue a new autonomous pipeline execution job."""
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO executions (id, project_id, user_id, status, attempt, created_at, last_heartbeat)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (execution_id, project_id, user_id, STATUS_QUEUED, now_iso, now_iso)
            )
            await db.commit()

            if TASK_WORKER_ENGINE == "arq":
                await self.enqueue_arq(execution_id, project_id, user_id)

            return await self.get_execution(execution_id)
        finally:
            await db.close()

    async def claim(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Claim the oldest QUEUED execution for worker_id."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id FROM executions WHERE status = ? ORDER BY created_at ASC LIMIT 1",
                (STATUS_QUEUED,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            
            exec_id = row["id"]
            await db.execute(
                """
                UPDATE executions 
                SET status = ?, worker_id = ?, started_at = ?, last_heartbeat = ?
                WHERE id = ? AND status = ?
                """,
                (STATUS_RUNNING, worker_id, now_iso, now_iso, exec_id, STATUS_QUEUED)
            )
            await db.commit()

            claimed = await self.get_execution(exec_id)
            if claimed and claimed["status"] == STATUS_RUNNING and claimed.get("worker_id") == worker_id:
                return claimed
            return None
        finally:
            await db.close()

    async def claim_execution(self, execution_id: str, worker_id: str) -> Optional[Dict[str, Any]]:
        """Claim a specific QUEUED execution for worker_id."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        try:
            await db.execute(
                """
                UPDATE executions 
                SET status = ?, worker_id = ?, started_at = ?, last_heartbeat = ?
                WHERE id = ? AND status = ?
                """,
                (STATUS_RUNNING, worker_id, now_iso, now_iso, execution_id, STATUS_QUEUED)
            )
            await db.commit()

            claimed = await self.get_execution(execution_id)
            if claimed and claimed["status"] == STATUS_RUNNING and claimed.get("worker_id") == worker_id:
                return claimed
            return None
        finally:
            await db.close()

    async def heartbeat(self, execution_id: str):
        """Update last_heartbeat timestamp for active execution."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        try:
            await db.execute(
                "UPDATE executions SET last_heartbeat = ? WHERE id = ?",
                (now_iso, execution_id)
            )
            await db.commit()
        finally:
            await db.close()

    async def mark_cancelling(self, execution_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Atomically transition execution state QUEUED/RUNNING -> CANCELLING."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        try:
            cursor = await db.execute(
                """
                UPDATE executions 
                SET status = ?, last_heartbeat = ?
                WHERE id = ? AND user_id = ? AND status IN (?, ?)
                """,
                (STATUS_CANCELLING, now_iso, execution_id, user_id, STATUS_QUEUED, STATUS_RUNNING)
            )
            await db.commit()
            return await self.get_execution(execution_id)
        finally:
            await db.close()

    async def cancel(self, execution_id: str) -> Dict[str, Any]:
        """Atomically transition execution state -> CANCELLED and update project status to 'cancelled'."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        try:
            exec_rec = await self.get_execution(execution_id)
            if exec_rec:
                project_id = exec_rec["project_id"]
                await db.execute(
                    """
                    UPDATE executions 
                    SET status = ?, completed_at = ?, last_heartbeat = ? 
                    WHERE id = ? AND status IN (?, ?, ?)
                    """,
                    (STATUS_CANCELLED, now_iso, now_iso, execution_id, STATUS_QUEUED, STATUS_RUNNING, STATUS_CANCELLING)
                )
                await db.execute(
                    "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
                    (ProjectStatus.CANCELLED.value, now_iso, project_id)
                )
                await db.commit()
            return await self.get_execution(execution_id)
        finally:
            await db.close()

    async def complete(self, execution_id: str) -> Dict[str, Any]:
        """Mark execution COMPLETED."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        try:
            await db.execute(
                "UPDATE executions SET status = ?, completed_at = ?, last_heartbeat = ? WHERE id = ?",
                (STATUS_COMPLETED, now_iso, now_iso, execution_id)
            )
            await db.commit()
            return await self.get_execution(execution_id)
        finally:
            await db.close()

    async def fail(self, execution_id: str, error: str) -> Dict[str, Any]:
        """Mark execution FAILED with error message."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        try:
            await db.execute(
                "UPDATE executions SET status = ?, error = ?, completed_at = ?, last_heartbeat = ? WHERE id = ?",
                (STATUS_FAILED, str(error), now_iso, now_iso, execution_id)
            )
            await db.commit()
            return await self.get_execution(execution_id)
        finally:
            await db.close()

    async def mark_recoverable(self, execution_id: str, reason: str) -> Dict[str, Any]:
        """Mark execution RECOVERABLE after crash or stale heartbeat."""
        now_iso = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        try:
            await db.execute(
                "UPDATE executions SET status = ?, error = ?, completed_at = ?, last_heartbeat = ? WHERE id = ?",
                (STATUS_RECOVERABLE, str(reason), now_iso, now_iso, execution_id)
            )
            await db.commit()
            return await self.get_execution(execution_id)
        finally:
            await db.close()

    async def get_execution(self, execution_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve execution record by ID, checking optional user ownership."""
        db = await get_db()
        try:
            if user_id:
                cursor = await db.execute(
                    "SELECT * FROM executions WHERE id = ? AND user_id = ?",
                    (execution_id, user_id)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM executions WHERE id = ?",
                    (execution_id,)
                )
            row = await cursor.fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            await db.close()

    async def list_project_executions(self, project_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all execution records for a project."""
        db = await get_db()
        try:
            if user_id:
                cursor = await db.execute(
                    "SELECT * FROM executions WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC",
                    (project_id, user_id)
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM executions WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,)
                )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()


# Global singleton queue instance
task_queue = TaskQueue()
