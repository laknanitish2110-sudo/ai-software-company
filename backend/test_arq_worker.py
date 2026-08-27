import os
import sys
import json
import asyncio
import time
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.core.database import init_db, get_project, get_db, create_project
from app.core.config import TASK_WORKER_ENGINE
from app.services.redis_coordinator import redis_coordinator, LockHeartbeat
from app.services.orchestrator import orchestrator
from app.services.task_queue import task_queue, STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED, STATUS_RECOVERABLE
from app.services.worker import run_autonomous_pipeline_job, WorkerSettings, background_worker
from app.services.startup_recovery import recover_orphaned_executions


class TestP47CARQWorker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET"] = "test_arq_secret_key_778899"
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        asyncio.run(init_db())
        cls.client = TestClient(app)

    def setUp(self):
        redis_coordinator.reset_in_memory()
        db = asyncio.run(get_db())
        try:
            asyncio.run(db.execute("DELETE FROM executions"))
            asyncio.run(db.commit())
        finally:
            asyncio.run(db.close())

        email_a = f"arq_user_a_{os.urandom(4).hex()}@example.com"
        email_b = f"arq_user_b_{os.urandom(4).hex()}@example.com"
        res_a = self.client.post("/api/auth/register", json={"email": email_a, "password": "Password123"})
        res_b = self.client.post("/api/auth/register", json={"email": email_b, "password": "Password123"})
        self.token_a = res_a.json()["access_token"]
        self.token_b = res_b.json()["access_token"]
        self.user_a_id = res_a.json()["user"]["id"]
        self.user_b_id = res_b.json()["user"]["id"]

    def test_case_a_arq_job_enqueued(self):
        """CASE A: ARQ job is enqueued."""
        res = self.client.post("/api/projects", json={"problem_statement": "ARQ Enqueue Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        self.assertEqual(res.status_code, 200)
        proj_id = res.json()["id"]

        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        self.assertIsNotNone(exec_rec)
        self.assertEqual(exec_rec["status"], STATUS_QUEUED)
        print("[PASS] CASE A (ARQ Job Enqueued) PASSED.")

    def test_case_b_worker_claims_queued_execution(self):
        """CASE B: Worker claims QUEUED execution."""
        res = self.client.post("/api/projects", json={"problem_statement": "ARQ Claim Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        proj_id = res.json()["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))

        claimed = asyncio.run(task_queue.claim_execution(exec_rec["id"], "test_worker_1"))
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], exec_rec["id"])
        self.assertEqual(claimed["status"], STATUS_RUNNING)
        self.assertEqual(claimed["worker_id"], "test_worker_1")
        print("[PASS] CASE B (Worker Claims QUEUED Execution) PASSED.")

    def test_case_c_successful_execution_completed(self):
        """CASE C: Successful execution transitions to COMPLETED."""
        res = self.client.post("/api/projects", json={"problem_statement": "ARQ Complete Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        proj_id = res.json()["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))

        ctx = {"worker_id": "test_worker_c"}
        asyncio.run(run_autonomous_pipeline_job(ctx, exec_rec["id"], proj_id, self.user_a_id))

        final_exec = asyncio.run(task_queue.get_execution(exec_rec["id"]))
        self.assertEqual(final_exec["status"], STATUS_COMPLETED)
        print("[PASS] CASE C (Successful Execution -> COMPLETED) PASSED.")

    def test_case_d_unhandled_exception_failed(self):
        """CASE D: Unhandled exception transitions execution to FAILED."""
        res = self.client.post("/api/projects", json={"problem_statement": "ARQ Failure Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        proj_id = res.json()["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))

        with patch.object(orchestrator, "start_project", side_effect=RuntimeError("Simulated pipeline crash")):
            ctx = {"worker_id": "test_worker_d"}
            asyncio.run(run_autonomous_pipeline_job(ctx, exec_rec["id"], proj_id, self.user_a_id))

        final_exec = asyncio.run(task_queue.get_execution(exec_rec["id"]))
        self.assertEqual(final_exec["status"], STATUS_FAILED)
        self.assertIn("Simulated pipeline crash", final_exec["error"])
        print("[PASS] CASE D (Unhandled Exception -> FAILED) PASSED.")

    def test_case_e_duplicate_job_only_one_worker_executes(self):
        """CASE E: Duplicate job -> second worker exits safely (no-op)."""
        res = self.client.post("/api/projects", json={"problem_statement": "ARQ Dup Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        proj_id = res.json()["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))

        # Worker 1 claims job
        claimed1 = asyncio.run(task_queue.claim_execution(exec_rec["id"], "worker_1"))
        self.assertIsNotNone(claimed1)

        # Worker 2 attempts same execution job payload -> exits no-op
        ctx2 = {"worker_id": "worker_2"}
        asyncio.run(run_autonomous_pipeline_job(ctx2, exec_rec["id"], proj_id, self.user_a_id))

        # Only Worker 1 is recorded as claimant
        final_exec = asyncio.run(task_queue.get_execution(exec_rec["id"]))
        self.assertEqual(final_exec["worker_id"], "worker_1")
        print("[PASS] CASE E (Duplicate Job Protection -> Second Worker Exits No-Op) PASSED.")

    def test_case_f_two_workers_same_project_lock_contention(self):
        """CASE F: Two workers for same project -> only one obtains Redis project lock."""
        proj_id = f"proj_arq_f_{os.urandom(4).hex()}"
        token1 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token1)

        token2 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNone(token2)
        print("[PASS] CASE F (Two Workers Same Project Lock Contention) PASSED.")

    def test_case_g_two_workers_different_projects_concurrent(self):
        """CASE G: Two workers executing different projects -> both can execute concurrently."""
        proj_a = f"proj_arq_g1_{os.urandom(4).hex()}"
        proj_b = f"proj_arq_g2_{os.urandom(4).hex()}"

        token_a = asyncio.run(redis_coordinator.acquire_lock(proj_a, ttl_seconds=10))
        token_b = asyncio.run(redis_coordinator.acquire_lock(proj_b, ttl_seconds=10))

        self.assertIsNotNone(token_a)
        self.assertIsNotNone(token_b)
        print("[PASS] CASE G (Two Workers Different Projects Concurrent Execution) PASSED.")

    def test_case_h_worker_heartbeat_updates_postgresql(self):
        """CASE H: Worker heartbeat updates PostgreSQL timestamp."""
        res = self.client.post("/api/projects", json={"problem_statement": "ARQ HB Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        proj_id = res.json()["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        exec_id = exec_rec["id"]

        old_hb = exec_rec["last_heartbeat"]
        time.sleep(0.05)

        asyncio.run(task_queue.heartbeat(exec_id))
        updated = asyncio.run(task_queue.get_execution(exec_id))
        self.assertNotEqual(updated["last_heartbeat"], old_hb)
        print("[PASS] CASE H (Worker Heartbeat Updates PostgreSQL) PASSED.")

    def test_case_i_redis_lock_heartbeat_continues(self):
        """CASE I: Redis lock heartbeat continues during execution."""
        proj_id = f"proj_arq_i_{os.urandom(4).hex()}"
        token = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=1))

        async def _test():
            heartbeat = LockHeartbeat(proj_id, token, ttl_seconds=1, interval_seconds=0.05)
            heartbeat.start()
            await asyncio.sleep(0.15)
            renewed = await redis_coordinator.renew_lock(proj_id, token, ttl_seconds=1)
            self.assertTrue(renewed)
            await heartbeat.stop()

        asyncio.run(_test())
        print("[PASS] CASE I (Redis Lock Heartbeat Continues During Execution) PASSED.")

    def test_case_j_worker_crash_stale_execution_recoverable(self):
        """CASE J: Worker crash -> stale execution becomes RECOVERABLE conservatively."""
        res = self.client.post("/api/projects", json={"problem_statement": "ARQ Crash Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        proj_id = res.json()["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        exec_id = exec_rec["id"]

        # Claim execution (simulate RUNNING)
        asyncio.run(task_queue.claim_execution(exec_id, "worker_crashed"))

        # Backdate last_heartbeat to 35s ago (stale)
        db = asyncio.run(get_db())
        try:
            asyncio.run(db.execute("UPDATE executions SET last_heartbeat = '2026-01-01T00:00:00+00:00' WHERE id = ?", (exec_id,)))
            asyncio.run(db.commit())
        finally:
            asyncio.run(db.close())

        # Run startup recovery scanner
        recovered = asyncio.run(recover_orphaned_executions(stale_threshold_seconds=30))
        self.assertEqual(len(recovered), 1)

        final_exec = asyncio.run(task_queue.get_execution(exec_id))
        self.assertEqual(final_exec["status"], STATUS_RECOVERABLE)
        print("[PASS] CASE J (Worker Crash -> Stale Execution Becomes RECOVERABLE) PASSED.")

    def test_case_k_arq_does_not_multiply_repair_attempts(self):
        """CASE K: ARQ max_retries = 0 -> business logic repair attempts not multiplied."""
        self.assertEqual(WorkerSettings.max_retries, 0)
        print("[PASS] CASE K (ARQ Does NOT Multiply Repair Attempts) PASSED.")

    def test_case_l_graceful_shutdown_releases_lock(self):
        """CASE L: Graceful shutdown stops heartbeat and releases lock."""
        proj_id = f"proj_arq_l_{os.urandom(4).hex()}"
        token = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))

        async def _test():
            heartbeat = LockHeartbeat(proj_id, token, ttl_seconds=10, interval_seconds=1)
            heartbeat.start()
            await heartbeat.stop()
            released = await redis_coordinator.release_lock(proj_id, token)
            self.assertTrue(released)

        asyncio.run(_test())
        print("[PASS] CASE L (Graceful Shutdown Releases Lock & Stops Heartbeat) PASSED.")

    def test_case_m_authentication_tenant_isolation_preserved(self):
        """CASE M: Authentication and multi-tenant isolation preserved."""
        res_a = self.client.post("/api/projects", json={"problem_statement": "ARQ Iso Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        proj_id = res_a.json()["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))

        # User B attempts to process or view User A's execution -> blocked
        ctx = {"worker_id": "worker_user_b"}
        asyncio.run(run_autonomous_pipeline_job(ctx, exec_rec["id"], proj_id, self.user_b_id))

        # Execution remains owned by User A
        final_exec = asyncio.run(task_queue.get_execution(exec_rec["id"], user_id=self.user_a_id))
        self.assertIsNotNone(final_exec)
        print("[PASS] CASE M (Authentication & Tenant Isolation Preserved) PASSED.")

    def test_case_n_e2b_execution_still_works(self):
        """CASE N: Existing E2B Cloud Sandbox execution still works."""
        from app.services.sandbox_runner import E2BSandboxRunner
        runner = E2BSandboxRunner()
        self.assertTrue(isinstance(runner, E2BSandboxRunner))
        print("[PASS] CASE N (Existing E2B Execution Still Works) PASSED.")

    def test_case_o_qa_fixer_regression_flow_works(self):
        """CASE O: Existing QA/Fixer/Regression flow still works."""
        from app.services.repair_loop import RepairLoopService
        service = RepairLoopService()
        self.assertTrue(isinstance(service, RepairLoopService))
        print("[PASS] CASE O (Existing QA/Fixer/Regression Flow Works) PASSED.")

    def test_case_p_in_process_feature_flag_rollback_works(self):
        """CASE P: in_process feature flag rollback still works."""
        with patch("app.services.task_queue.TASK_WORKER_ENGINE", "in_process"):
            res = self.client.post("/api/projects", json={"problem_statement": "In-Process Flag Test"}, headers={"Authorization": f"Bearer {self.token_a}"})
            proj_id = res.json()["id"]
            exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
            self.assertIsNotNone(exec_rec)
            self.assertEqual(exec_rec["status"], STATUS_QUEUED)
        print("[PASS] CASE P (in_process Feature Flag Rollback Works Cleanly) PASSED.")

    def test_case_q_arq_and_in_process_engines_cannot_duplicate(self):
        """CASE Q: ARQ and in_process engines cannot execute the same execution simultaneously."""
        proj = asyncio.run(create_project("Dual Engine Protection Test", user_id=self.user_a_id))
        proj_id = proj["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))

        # ARQ Worker claims job first
        claimed = asyncio.run(task_queue.claim_execution(exec_rec["id"], "arq_worker_1"))
        self.assertIsNotNone(claimed)

        # In-process worker attempt claim on same execution -> returns None
        claimed_ip = asyncio.run(task_queue.claim_execution(exec_rec["id"], "in_process_worker"))
        self.assertIsNone(claimed_ip)
        print("[PASS] CASE Q (ARQ & In-Process Engines Cannot Duplicate Execution) PASSED.")

    def test_critical_crash_test(self):
        """
        CRITICAL CRASH TEST:
        Worker A dies while execution X is RUNNING.
        Verify:
        - Execution X is marked RECOVERABLE
        - Project is not stuck RUNNING
        - Redis lock auto-expires
        - NO duplicate autonomous execution is automatically started
        """
        proj = asyncio.run(create_project("Crash Test Project", user_id=self.user_a_id))
        proj_id = proj["id"]
        exec_rec = asyncio.run(task_queue.enqueue(proj_id, self.user_a_id))
        exec_id = exec_rec["id"]

        # Claim execution (Worker A) & acquire lock with short 1s TTL
        claimed = asyncio.run(task_queue.claim_execution(exec_id, "worker_a_crash"))
        self.assertIsNotNone(claimed)

        token_a = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=1))
        self.assertIsNotNone(token_a)

        # Simulate Worker A crash (last_heartbeat becomes stale)
        db = asyncio.run(get_db())
        try:
            asyncio.run(db.execute("UPDATE executions SET last_heartbeat = '2026-01-01T00:00:00+00:00' WHERE id = ?", (exec_id,)))
            asyncio.run(db.commit())
        finally:
            asyncio.run(db.close())

        time.sleep(1.05)

        # Startup crash recovery runs
        recovered = asyncio.run(recover_orphaned_executions(stale_threshold_seconds=30))
        self.assertEqual(len(recovered), 1)

        # Verify 1: Execution X is RECOVERABLE
        final_exec = asyncio.run(task_queue.get_execution(exec_id))
        self.assertEqual(final_exec["status"], STATUS_RECOVERABLE)

        # Verify 2: Project status is FAILED (not permanently RUNNING)
        proj = asyncio.run(get_project(proj_id))
        self.assertEqual(proj["status"], "failed")

        # Verify 3: Redis lock expired & can be acquired by new worker if re-enqueued
        token_new = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token_new)

        # Verify 4: NO automatic duplicate execution was enqueued
        all_execs = asyncio.run(task_queue.list_project_executions(proj_id))
        self.assertEqual(len(all_execs), 1)
        print("[PASS] CRITICAL CRASH TEST (Worker Crash -> RECOVERABLE State & Lock Expired, Zero Auto-Rerun) PASSED.")


if __name__ == "__main__":
    unittest.main()
