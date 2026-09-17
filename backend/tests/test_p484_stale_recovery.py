import os
import json
import asyncio
import unittest
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.core.database import init_db, get_db, save_execution_event
from app.services.redis_coordinator import redis_coordinator
from app.services.recovery_worker import StaleExecutionRecoveryWorker


class TestP484StaleRecovery(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        os.environ["ENVIRONMENT"] = "development"
        await init_db()
        redis_coordinator.reset_in_memory()
        self.project_id = f"test_p484_proj_{os.urandom(4).hex()}"
        self.exec_id = f"test_p484_exec_{os.urandom(4).hex()}"

    async def test_case_1_sequence_fallback_sync_from_db(self):
        """Case 1: Ensure missing sequence counter initializes from DB MAX(seq) avoiding overlaps."""
        # Insert 3 DB events manually
        await save_execution_event(self.project_id, self.exec_id, 1, "e1", {"msg": 1})
        await save_execution_event(self.project_id, self.exec_id, 2, "e2", {"msg": 2})
        await save_execution_event(self.project_id, self.exec_id, 3, "e3", {"msg": 3})

        # Next sequence call on fresh in-memory coordinator should sync and return 4
        seq = await redis_coordinator.next_sequence(self.project_id)
        self.assertEqual(seq, 4)

    async def test_case_2_stale_running_recovery_sweep(self):
        """Case 2: Background worker recovers stale RUNNING execution (>30s old) to RECOVERABLE/FAILED."""
        db = await get_db()
        try:
            now = datetime.now(timezone.utc)
            stale_hb = (now - timedelta(seconds=60)).isoformat()
            ts = now.isoformat()

            await db.execute("INSERT INTO projects (id, problem_statement, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                            (self.project_id, "Test P484", "executing", ts, ts))
            await db.execute("INSERT INTO executions (id, project_id, user_id, status, last_heartbeat, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (self.exec_id, self.project_id, "user1", "RUNNING", stale_hb, ts))
            await db.commit()
        finally:
            await db.close()

        worker = StaleExecutionRecoveryWorker(interval_seconds=1, stale_running_seconds=30)
        recovered = await worker.perform_recovery_sweep()

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["id"], self.exec_id)
        self.assertEqual(recovered[0]["status"], "RECOVERABLE")

        # Verify project status updated to failed
        db = await get_db()
        try:
            cur = await db.execute("SELECT status FROM projects WHERE id = ?", (self.project_id,))
            p_row = await cur.fetchone()
            self.assertEqual(p_row["status"], "failed")
        finally:
            await db.close()

    async def test_case_3_stale_cancelling_recovery_sweep(self):
        """Case 3: Background worker recovers stale CANCELLING execution to CANCELLED."""
        db = await get_db()
        try:
            now = datetime.now(timezone.utc)
            stale_hb = (now - timedelta(seconds=60)).isoformat()
            ts = now.isoformat()

            await db.execute("INSERT INTO projects (id, problem_statement, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                            (self.project_id, "Test P484 Cancelling", "executing", ts, ts))
            await db.execute("INSERT INTO executions (id, project_id, user_id, status, last_heartbeat, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (self.exec_id, self.project_id, "user1", "CANCELLING", stale_hb, ts))
            await db.commit()
        finally:
            await db.close()

        worker = StaleExecutionRecoveryWorker(interval_seconds=1, stale_running_seconds=30)
        recovered = await worker.perform_recovery_sweep()

        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["id"], self.exec_id)
        self.assertEqual(recovered[0]["status"], "CANCELLED")

    async def test_case_4_multi_worker_lock_safety(self):
        """Case 4: Redis lock prevents concurrent workers from racing on recovery sweep."""
        # Hold sweep lock
        token = await redis_coordinator.acquire_lock("recovery:worker:sweep", ttl_seconds=30)
        self.assertIsNotNone(token)

        worker = StaleExecutionRecoveryWorker(interval_seconds=1)
        recovered = await worker.perform_recovery_sweep()
        self.assertEqual(len(recovered), 0)

        await redis_coordinator.release_lock("recovery:worker:sweep", token)


if __name__ == "__main__":
    unittest.main()
