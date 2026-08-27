"""
Startup Crash Recovery Service (P4.5)

Runs on application startup to detect orphaned project executions caused by
abrupt server process restarts, crashes, or unhandled worker terminations.
Fails closed conservatively: marks orphaned executions RECOVERABLE/FAILED
and updates project database status to FAILED without auto-rerunning expensive operations.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from app.core.database import get_db
from app.models.schemas import ProjectStatus
from app.services.task_queue import task_queue, STATUS_RUNNING, STATUS_QUEUED, STATUS_RECOVERABLE, STATUS_CANCELLING, STATUS_CANCELLED

logger = logging.getLogger(__name__)


async def recover_orphaned_executions(stale_threshold_seconds: int = 30, queued_stale_threshold_seconds: int = 300) -> List[Dict[str, Any]]:
    """
    Scans for executions in RUNNING state (stale heartbeat > 30s), CANCELLING state (stale > 30s), or QUEUED state (created > 300s ago).
    Updates execution state to RECOVERABLE or CANCELLED conservatively without auto-rerunning.
    """
    db = await get_db()
    recovered: List[Dict[str, Any]] = []
    
    try:
        # Find active/queued/cancelling executions
        cursor = await db.execute(
            "SELECT id, project_id, status, created_at, last_heartbeat FROM executions WHERE status IN (?, ?, ?)",
            (STATUS_RUNNING, STATUS_QUEUED, STATUS_CANCELLING)
        )
        rows = await cursor.fetchall()
        
        now = datetime.now(timezone.utc)
        running_cutoff = now - timedelta(seconds=stale_threshold_seconds)
        queued_cutoff = now - timedelta(seconds=queued_stale_threshold_seconds)

        for row in rows:
            exec_id = row["id"]
            project_id = row["project_id"]
            status = row["status"]
            created_at_str = row["created_at"]
            last_hb_str = row["last_heartbeat"]
            
            is_stale = False
            if status == STATUS_QUEUED:
                if created_at_str:
                    try:
                        c_dt = datetime.fromisoformat(created_at_str)
                        if c_dt.tzinfo is None:
                            c_dt = c_dt.replace(tzinfo=timezone.utc)
                        if c_dt < queued_cutoff:
                            is_stale = True
                    except Exception:
                        pass
            elif status in (STATUS_RUNNING, STATUS_CANCELLING):
                if not last_hb_str:
                    is_stale = True
                else:
                    try:
                        hb_dt = datetime.fromisoformat(last_hb_str)
                        if hb_dt.tzinfo is None:
                            hb_dt = hb_dt.replace(tzinfo=timezone.utc)
                        if hb_dt < running_cutoff:
                            is_stale = True
                    except Exception:
                        is_stale = True

            if is_stale:
                if status == STATUS_CANCELLING:
                    reason = f"Process crash recovery: Orphaned CANCELLING execution {exec_id} marked CANCELLED."
                    logger.warning(reason)
                    rec = await task_queue.cancel(exec_id)
                    recovered.append(rec)
                else:
                    reason = f"Process crash recovery: Orphaned execution {exec_id} (last heartbeat: {last_hb_str}) marked RECOVERABLE."
                    logger.warning(reason)
                    rec = await task_queue.mark_recoverable(exec_id, reason)
                    recovered.append(rec)
                    await db.execute(
                        "UPDATE projects SET status = ?, updated_at = ? WHERE id = ? AND status NOT IN ('completed', 'failed', 'cancelled')",
                        (ProjectStatus.FAILED.value, now.isoformat(), project_id)
                    )

        # Also sweep any orphaned projects stuck in active states with no active execution
        await db.execute(
            """
            UPDATE projects 
            SET status = ?, updated_at = ? 
            WHERE status IN ('running', 'executing', 'repairing')
              AND id NOT IN (SELECT project_id FROM executions WHERE status = 'RUNNING')
            """,
            (ProjectStatus.FAILED.value, now.isoformat())
        )
        await db.commit()
        
        if recovered:
            logger.info(f"Startup crash recovery recovered {len(recovered)} orphaned execution(s).")
        return recovered
    finally:
        await db.close()
