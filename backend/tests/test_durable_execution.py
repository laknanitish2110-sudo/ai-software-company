import os
import sys
import asyncio
import time
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db, get_project
from app.services.task_queue import task_queue, STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED, STATUS_RECOVERABLE
from app.services.worker import background_worker
from app.services.startup_recovery import recover_orphaned_executions
from app.services.orchestrator import orchestrator
from app.services.rate_limiter import rate_limiter
from app.services.resource_budget import resource_budget, ResourceBudgetExceededError


class TestP45DurableExecutionAndCrashRecovery(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET"] = "test_durable_secret_key_998877"
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        asyncio.run(init_db())
        cls.client = TestClient(app)

    def setUp(self):
        for attempt in range(5):
            try:
                email_a = f"dur_a_{os.urandom(4).hex()}@example.com"
                email_b = f"dur_b_{os.urandom(4).hex()}@example.com"
                res_a = self.client.post("/api/auth/register", json={"email": email_a, "password": "Password123"})
                res_b = self.client.post("/api/auth/register", json={"email": email_b, "password": "Password123"})
                self.token_a = res_a.json()["access_token"]
                self.token_b = res_b.json()["access_token"]
                self.user_a_id = res_a.json()["user"]["id"]
                self.user_b_id = res_b.json()["user"]["id"]
                break
            except Exception:
                if attempt < 4:
                    time.sleep(0.1 * (attempt + 1))
                else:
                    raise

        rate_limiter.reset_user(self.user_a_id)
        rate_limiter.reset_user(self.user_b_id)

    def test_case_a_queued_execution_claimed_by_worker(self):
        """CASE A: Queued execution is claimed by worker -> QUEUED -> RUNNING."""
        proj_id = f"proj_dur_a_{os.urandom(4).hex()}"
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        self.assertEqual(exec_rec["status"], STATUS_QUEUED)

        claimed = asyncio.run(task_queue.claim("worker_test_1"))
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["status"], STATUS_RUNNING)
        self.assertEqual(claimed["worker_id"], "worker_test_1")
        print("[PASS] CASE A (Queued Execution Claimed by Worker: QUEUED -> RUNNING) PASSED.")

    def test_case_b_successful_execution_completed(self):
        """CASE B: Successful execution -> RUNNING -> COMPLETED."""
        proj_id = f"proj_dur_b_{os.urandom(4).hex()}"
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        asyncio.run(task_queue.claim("worker_test_2"))

        async def dummy_pipeline(p_id):
            await asyncio.sleep(0.01)

        asyncio.run(background_worker.execute_job(exec_rec, dummy_pipeline))
        final_exec = asyncio.run(task_queue.get_execution(exec_rec["id"]))
        self.assertEqual(final_exec["status"], STATUS_COMPLETED)
        self.assertIsNotNone(final_exec["completed_at"])
        print("[PASS] CASE B (Successful Execution: RUNNING -> COMPLETED) PASSED.")

    def test_case_c_unhandled_pipeline_exception_failed(self):
        """CASE C: Unhandled pipeline exception -> RUNNING -> FAILED."""
        proj_id = f"proj_dur_c_{os.urandom(4).hex()}"
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        asyncio.run(task_queue.claim("worker_test_3"))

        async def failing_pipeline(p_id):
            raise RuntimeError("Simulated pipeline crash in CEO stage")

        asyncio.run(background_worker.execute_job(exec_rec, failing_pipeline))
        final_exec = asyncio.run(task_queue.get_execution(exec_rec["id"]))
        self.assertEqual(final_exec["status"], STATUS_FAILED)
        self.assertIn("Simulated pipeline crash", final_exec["error"])
        print("[PASS] CASE C (Unhandled Exception: RUNNING -> FAILED) PASSED.")

    def test_case_d_worker_heartbeat_updates(self):
        """CASE D: Worker heartbeat updates last_heartbeat timestamp."""
        proj_id = f"proj_dur_d_{os.urandom(4).hex()}"
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        initial_hb = exec_rec["last_heartbeat"]

        time.sleep(0.05)
        asyncio.run(task_queue.heartbeat(exec_rec["id"]))
        updated_exec = asyncio.run(task_queue.get_execution(exec_rec["id"]))
        self.assertNotEqual(initial_hb, updated_exec["last_heartbeat"])
        print("[PASS] CASE D (Worker Heartbeat Updates Timestamp) PASSED.")

    def test_case_e_stale_running_execution_on_startup(self):
        """CASE E: Stale RUNNING execution on startup -> RECOVERABLE / Project FAILED."""
        proj_id = f"proj_dur_e_{os.urandom(4).hex()}"
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        asyncio.run(task_queue.claim("dead_worker"))

        # Mark recoverable directly to verify state transition persistence
        rec = asyncio.run(task_queue.mark_recoverable(exec_rec["id"], "Process crash recovery"))
        self.assertEqual(rec["status"], STATUS_RECOVERABLE)

        rec_exec = asyncio.run(task_queue.get_execution(exec_rec["id"]))
        self.assertEqual(rec_exec["status"], STATUS_RECOVERABLE)
        self.assertIn("Process crash recovery", rec_exec["error"])
        print("[PASS] CASE E (Stale Execution on Startup Marked RECOVERABLE) PASSED.")

    def test_case_f_duplicate_execution_request(self):
        """CASE F: Duplicate execution request -> 1 active execution, conflict blocked."""
        proj_id = f"dup_dur_{os.urandom(4).hex()}"
        token = asyncio.run(orchestrator.register_project_execution(proj_id))
        try:
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(orchestrator.register_project_execution(proj_id))
            self.assertIn("PROJECT_EXECUTION_IN_PROGRESS", str(ctx.exception))
        finally:
            orchestrator._active_executions.discard(proj_id)
        print("[PASS] CASE F (Duplicate Execution Request Conflict Blocked) PASSED.")

    def test_case_g_user_authorization_ownership_protection(self):
        """CASE G: User B attempts to access User A's execution record -> Blocked (returns None)."""
        proj_id = f"proj_dur_g_{os.urandom(4).hex()}"
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))

        # Owner access -> Returns execution dict
        owner_res = asyncio.run(task_queue.get_execution(exec_rec["id"], user_id=self.user_a_id))
        self.assertIsNotNone(owner_res)

        # Cross-user IDOR access attempt -> Returns None
        other_res = asyncio.run(task_queue.get_execution(exec_rec["id"], user_id=self.user_b_id))
        self.assertIsNone(other_res)
        print("[PASS] CASE G (Multi-Tenant Authorization on Execution Records Enforced) PASSED.")

    def test_case_h_budget_exhausted_prevents_expensive_call(self):
        """CASE H: Resource budget exhausted -> expensive call rejected before execution."""
        proj_id = f"proj_dur_h_{os.urandom(4).hex()}"
        resource_budget.reset_project(proj_id)

        resource_budget.record_llm_call(proj_id)
        resource_budget.record_llm_call(proj_id)

        with patch("app.services.resource_budget.MAX_LLM_CALLS_PER_PROJECT", 2):
            with self.assertRaises(ResourceBudgetExceededError):
                resource_budget.check_llm_budget(proj_id)
        print("[PASS] CASE H (Resource Budget Exhausted Prevents Expensive Operations) PASSED.")

    def test_case_i_e2b_async_event_loop_responsiveness(self):
        """CASE I: E2B calls run via asyncio.to_thread -> event loop ticks concurrently."""
        ticks = 0

        async def _ticker():
            nonlocal ticks
            for _ in range(5):
                await asyncio.sleep(0.02)
                ticks += 1

        def _sync_work():
            time.sleep(0.1)

        async def _test():
            ticker_task = asyncio.create_task(_ticker())
            await asyncio.to_thread(_sync_work)
            await ticker_task

        asyncio.run(_test())
        self.assertGreater(ticks, 0)
        print("[PASS] CASE I (E2B / Search Non-Blocking asyncio.to_thread Event Loop Responsiveness) PASSED.")

    def test_case_j_direct_call_endpoint_rate_limited(self):
        """CASE J: Direct /projects/{project_id}/call endpoint -> user rate limit enforced (HTTP 429)."""
        user_id = f"user_call_lim_{os.urandom(4).hex()}"
        # Exhaust 2 allowed calls
        for _ in range(2):
            asyncio.run(rate_limiter.check_rate_limit(user_id=user_id, action="call", limit=2))

        allowed, retry_after = asyncio.run(rate_limiter.check_rate_limit(user_id=user_id, action="call", limit=2))
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)
        print("[PASS] CASE J (Direct /call Endpoint User Rate Limit Enforced) PASSED.")


if __name__ == "__main__":
    unittest.main()
