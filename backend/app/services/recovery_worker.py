"""
Decoupled Scheduled Stale Execution Recovery Worker (P4.8.2 / Step 4)

Runs periodically in the background (every 15s) independently of web process restarts.
Sweeps stale RUNNING, CANCELLING, and QUEUED executions using distributed locks and atomic DB claims.
Performs state transitions, releases execution locks, and emits durable WS notification events.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any

from app.core.config import get_environment
from app.core.database import claim_and_recover_stale_executions
from app.services.redis_coordinator import redis_coordinator

logger = logging.getLogger(__name__)


class StaleExecutionRecoveryWorker:
    """
    Scheduled background worker recovering orphaned/stale executions.
    Hardened for multi-worker safety, Redis lock coordination, and graceful shutdown.
    """
    def __init__(self, interval_seconds: int = 15, stale_running_seconds: int = 30, stale_queued_seconds: int = 300):
        self.interval_seconds = interval_seconds
        self.stale_running_seconds = stale_running_seconds
        self.stale_queued_seconds = stale_queued_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"StaleExecutionRecoveryWorker started (interval={self.interval_seconds}s).")

    async def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("StaleExecutionRecoveryWorker stopped cleanly.")

    async def _run_loop(self):
        while self._running:
            try:
                await self.perform_recovery_sweep()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during stale execution recovery sweep: {e}")
            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    async def perform_recovery_sweep(self) -> List[Dict[str, Any]]:
        """
        Executes single recovery sweep with Redis lock guard and atomic DB claims.
        """
        token = await redis_coordinator.acquire_lock("recovery:worker:sweep", ttl_seconds=10)
        if not token and get_environment() == "production":
            return []  # Another node is currently sweeping

        try:
            claimed = await claim_and_recover_stale_executions(
                stale_running_seconds=self.stale_running_seconds,
                stale_queued_seconds=self.stale_queued_seconds
            )
            for item in claimed:
                exec_id = item["id"]
                project_id = item["project_id"]
                status = item["status"]

                try:
                    await redis_coordinator.force_release_lock(project_id)
                except Exception:
                    pass

                if status == "CANCELLED":
                    logger.warning(f"Recovery worker: Stale CANCELLING execution {exec_id} recovered to CANCELLED.")
                    await redis_coordinator.publish_event_durable(
                        project_id, "cancellation_completed",
                        {"execution_id": exec_id, "reason": "Background stale recovery sweep"},
                        execution_id=exec_id
                    )
                else:
                    logger.warning(f"Recovery worker: Stale execution {exec_id} recovered to RECOVERABLE/FAILED.")
                    await redis_coordinator.publish_event_durable(
                        project_id, "execution_failed",
                        {"execution_id": exec_id, "reason": "Worker process crash or lost heartbeat"},
                        execution_id=exec_id
                    )
            return claimed
        finally:
            if token:
                try:
                    await redis_coordinator.release_lock("recovery:worker:sweep", token)
                except Exception:
                    pass


stale_recovery_worker = StaleExecutionRecoveryWorker()
