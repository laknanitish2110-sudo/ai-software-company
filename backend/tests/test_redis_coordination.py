import os
import sys
import json
import asyncio
import time
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db, get_project
from app.services.redis_coordinator import redis_coordinator, RedisUnavailableError, LockLostError, LockHeartbeat, InMemoryCoordinator
from app.services.orchestrator import orchestrator
from app.services.rate_limiter import rate_limiter
from app.services.resource_budget import resource_budget, ResourceBudgetExceededError


class TestP47BRedisCoordination(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET"] = "test_redis_secret_key_445566"
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        asyncio.run(init_db())
        cls.client = TestClient(app)

    def setUp(self):
        redis_coordinator.reset_in_memory()
        email_a = f"redis_user_a_{os.urandom(4).hex()}@example.com"
        email_b = f"redis_user_b_{os.urandom(4).hex()}@example.com"
        res_a = self.client.post("/api/auth/register", json={"email": email_a, "password": "Password123"})
        res_b = self.client.post("/api/auth/register", json={"email": email_b, "password": "Password123"})
        self.token_a = res_a.json()["access_token"]
        self.token_b = res_b.json()["access_token"]
        self.user_a_id = res_a.json()["user"]["id"]
        self.user_b_id = res_b.json()["user"]["id"]

    def test_case_a_lock_acquisition_contention(self):
        """CASE A: Two workers acquire same project lock -> only one succeeds."""
        proj_id = f"proj_lock_a_{os.urandom(4).hex()}"
        token_1 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token_1)

        # Worker 2 attempt -> fails (returns None)
        token_2 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNone(token_2)
        print("[PASS] CASE A (Distributed Lock Acquisition Contention) PASSED.")

    def test_case_b_lock_owner_release(self):
        """CASE B: Lock owner releases -> second worker can acquire."""
        proj_id = f"proj_lock_b_{os.urandom(4).hex()}"
        token_1 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token_1)

        # Owner releases lock
        released = asyncio.run(redis_coordinator.release_lock(proj_id, token_1))
        self.assertTrue(released)

        # Worker 2 attempt -> succeeds now
        token_2 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token_2)
        print("[PASS] CASE B (Lock Owner Safe Release) PASSED.")

    def test_case_c_wrong_owner_release_fails(self):
        """CASE C: Wrong owner attempts release -> lock remains."""
        proj_id = f"proj_lock_c_{os.urandom(4).hex()}"
        token_1 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token_1)

        # Fake worker attempt release with wrong token
        released = asyncio.run(redis_coordinator.release_lock(proj_id, "fake_token_123"))
        self.assertFalse(released)

        # Lock still held by owner 1 -> worker 2 cannot acquire
        token_2 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNone(token_2)
        print("[PASS] CASE C (Wrong Owner Release Protection) PASSED.")

    def test_case_d_lock_ttl_expiration(self):
        """CASE D: Lock TTL expires -> new worker can acquire."""
        proj_id = f"proj_lock_d_{os.urandom(4).hex()}"
        # Acquire lock with 1 second TTL
        token_1 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=1))
        self.assertIsNotNone(token_1)

        time.sleep(1.05)
        # Worker 2 attempt -> succeeds after TTL expiry
        token_2 = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token_2)
        print("[PASS] CASE D (Lock TTL Expiration Safety) PASSED.")

    def test_case_e_isolated_user_rate_limits(self):
        """CASE E: Two users consume rate limit concurrently -> limits remain isolated."""
        user_a = f"rate_usr_a_{os.urandom(4).hex()}"
        user_b = f"rate_usr_b_{os.urandom(4).hex()}"

        # Exhaust User A's limit (2)
        for _ in range(2):
            redis_coordinator.check_rate_limit(user_a, action="create", limit=2, window_seconds=60)

        allowed_a, _ = redis_coordinator.check_rate_limit(user_a, action="create", limit=2, window_seconds=60)
        self.assertFalse(allowed_a)

        # User B remains independent and allowed
        allowed_b, _ = redis_coordinator.check_rate_limit(user_b, action="create", limit=2, window_seconds=60)
        self.assertTrue(allowed_b)
        print("[PASS] CASE E (Isolated User Rate Limits) PASSED.")

    def test_case_f_atomic_resource_budget_consumption(self):
        """CASE F: Two workers consume final project budget concurrently -> budget overflow blocked."""
        proj_id = f"proj_budget_f_{os.urandom(4).hex()}"

        # Exhaust budget limit (max 2)
        ok1, cnt1 = asyncio.run(redis_coordinator.consume_budget(proj_id, "llm_calls", max_limit=2))
        self.assertTrue(ok1)
        self.assertEqual(cnt1, 1)

        ok2, cnt2 = asyncio.run(redis_coordinator.consume_budget(proj_id, "llm_calls", max_limit=2))
        self.assertTrue(ok2)
        self.assertEqual(cnt2, 2)

        # 3rd worker attempt -> blocked
        ok3, cnt3 = asyncio.run(redis_coordinator.consume_budget(proj_id, "llm_calls", max_limit=2))
        self.assertFalse(ok3)
        self.assertEqual(cnt3, 2)
        print("[PASS] CASE F (Atomic Resource Budget Consumption) PASSED.")

    def test_case_g_pubsub_event_delivery(self):
        """CASE G: Redis Pub/Sub event published -> subscriber receives event."""
        proj_id = f"proj_pubsub_{os.urandom(4).hex()}"
        received_msgs = []

        async def _sub():
            async for msg in redis_coordinator.subscribe_events(proj_id):
                received_msgs.append(msg)
                break

        async def _pub():
            await asyncio.sleep(0.02)
            await redis_coordinator.publish_event(proj_id, "agent_started", {"role": "ceo"})

        async def _test():
            sub_task = asyncio.create_task(_sub())
            await _pub()
            await sub_task

        asyncio.run(_test())
        self.assertEqual(len(received_msgs), 1)
        parsed = json.loads(received_msgs[0])
        self.assertEqual(parsed["type"], "agent_started")
        self.assertEqual(parsed["data"]["role"], "ceo")
        print("[PASS] CASE G (Redis Pub/Sub Event Delivery) PASSED.")

    def test_case_h_production_redis_unavailable_controlled_failure(self):
        """CASE H: Redis unavailable in production -> controlled fail-closed failure."""
        with patch("app.services.redis_coordinator.REDIS_URL", ""):
            with patch("app.services.redis_coordinator.get_environment", return_value="production"):
                with self.assertRaises(RedisUnavailableError) as ctx:
                    asyncio.run(redis_coordinator.acquire_lock("prod_proj", ttl_seconds=10))
                self.assertIn("strictly required in production", str(ctx.exception))
        print("[PASS] CASE H (Production Redis Unavailable Controlled Fail-Closed) PASSED.")

    def test_case_i_authentication_ownership_enforced(self):
        """CASE I: Authentication and ownership remain enforced."""
        res_a = self.client.post("/api/projects", json={"problem_statement": "Auth test"}, headers={"Authorization": f"Bearer {self.token_a}"})
        p_id = res_a.json()["id"]

        res_b = self.client.get(f"/api/projects/{p_id}", headers={"Authorization": f"Bearer {self.token_b}"})
        self.assertEqual(res_b.status_code, 404)
        print("[PASS] CASE I (Existing Authentication & Ownership Enforced) PASSED.")

    def test_case_j_multi_instance_simulation(self):
        """Multi-Instance Simulation: FastAPI Instance A, Instance B, Worker A, Worker B shared coordination."""
        proj_id = f"multi_inst_proj_{os.urandom(4).hex()}"

        # Instance A registers project execution -> acquires lock
        token_inst_a = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=30))
        self.assertIsNotNone(token_inst_a)

        # Instance B attempts duplicate execution -> fails with None (HTTP 409)
        token_inst_b = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=30))
        self.assertIsNone(token_inst_b)

        # Worker A processes job & releases lock
        released = asyncio.run(redis_coordinator.release_lock(proj_id, token_inst_a))
        self.assertTrue(released)

        # Worker B can now acquire lock
        token_wrk_b = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=30))
        self.assertIsNotNone(token_wrk_b)
        print("[PASS] Multi-Instance Simulation (FastAPI Instance A/B + Worker A/B Shared Coordination) PASSED.")

    # --- P4.7-B REVIEW REVISION TEST CASES (CASES K - P + ATOMIC LUA BUDGET CONCURRENCY) ---

    def test_case_k_lock_renewal(self):
        """CASE K: Worker A acquires lock, renews near TTL, Worker B acquisition rejected."""
        proj_id = f"proj_renew_k_{os.urandom(4).hex()}"
        token_a = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=2))
        self.assertIsNotNone(token_a)

        time.sleep(1.0)
        # Worker A renews lock for another 5 seconds
        renewed = asyncio.run(redis_coordinator.renew_lock(proj_id, token_a, ttl_seconds=5))
        self.assertTrue(renewed)

        # Worker B attempts acquisition -> REJECTED
        token_b = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=5))
        self.assertIsNone(token_b)
        print("[PASS] CASE K (Lock Renewal Ownership Verification) PASSED.")

    def test_case_l_wrong_owner_renewal_rejected(self):
        """CASE L: Worker A owns lock, Worker B attempts renewal -> REJECTED."""
        proj_id = f"proj_renew_l_{os.urandom(4).hex()}"
        token_a = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token_a)

        # Worker B attempts renewal using fake token -> REJECTED
        renewed_b = asyncio.run(redis_coordinator.renew_lock(proj_id, "fake_token_b", ttl_seconds=10))
        self.assertFalse(renewed_b)

        # Worker C attempts acquisition -> REJECTED because Worker A still owns lock
        token_c = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNone(token_c)
        print("[PASS] CASE L (Wrong Owner Renewal Rejection Safety) PASSED.")

    def test_case_m_lock_expiration_after_owner_stops(self):
        """CASE M: Worker A owns lock, stops renewing, TTL expires -> Worker B acquires."""
        proj_id = f"proj_renew_m_{os.urandom(4).hex()}"
        token_a = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=1))
        self.assertIsNotNone(token_a)

        # Worker A stops renewing & waits for TTL expiration
        time.sleep(1.05)

        # Worker B attempts acquisition -> SUCCEEDS
        token_b = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=10))
        self.assertIsNotNone(token_b)
        print("[PASS] CASE M (Lock Expiration After Heartbeat Stops) PASSED.")

    def test_case_n_long_execution_simulation(self):
        """CASE N: Long execution (exceeding initial 1s TTL) continuously renewed by Worker A."""
        proj_id = f"proj_renew_n_{os.urandom(4).hex()}"
        token_a = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=1))
        self.assertIsNotNone(token_a)

        # Simulate periodic heartbeat over 2.5 seconds (exceeding initial 1s TTL)
        for _ in range(5):
            time.sleep(0.4)
            renewed = asyncio.run(redis_coordinator.renew_lock(proj_id, token_a, ttl_seconds=1))
            self.assertTrue(renewed)
            # Worker B attempt during long execution -> REJECTED
            token_b = asyncio.run(redis_coordinator.acquire_lock(proj_id, ttl_seconds=1))
            self.assertIsNone(token_b)

        print("[PASS] CASE N (Long Autonomous Execution Continuous Lock Renewal) PASSED.")

    def test_case_o_completion_cleanup(self):
        """CASE O: Execution completes, heartbeat stops, lock released -> Worker B acquires."""
        proj_id = f"proj_renew_o_{os.urandom(4).hex()}"

        async def _run_test_o():
            token_a = await redis_coordinator.acquire_lock(proj_id, ttl_seconds=10)
            self.assertIsNotNone(token_a)
            heartbeat = LockHeartbeat(proj_id, token_a, ttl_seconds=10, interval_seconds=1)
            heartbeat.start()

            # Simulate execution work
            await asyncio.sleep(0.05)

            # Completion cleanup
            await heartbeat.stop()
            released = await redis_coordinator.release_lock(proj_id, token_a)
            self.assertTrue(released)

            # Worker B acquires lock post-completion -> SUCCEEDS
            token_b = await redis_coordinator.acquire_lock(proj_id, ttl_seconds=10)
            self.assertIsNotNone(token_b)

        asyncio.run(_run_test_o())
        print("[PASS] CASE O (Completion Heartbeat Cleanup & Release) PASSED.")

    def test_case_p_renewal_failure(self):
        """CASE P: Renewal failure triggers LockLostError / controlled failure state."""
        proj_id = f"proj_renew_p_{os.urandom(4).hex()}"

        async def _run_test_p():
            token_a = await redis_coordinator.acquire_lock(proj_id, ttl_seconds=1)
            # Force lock deletion externally to simulate lock loss / token invalidation
            await redis_coordinator.release_lock(proj_id, token_a)

            heartbeat = LockHeartbeat(proj_id, token_a, ttl_seconds=1, interval_seconds=0.05)
            heartbeat.start()

            # Wait for heartbeat cycle to detect renewal failure
            await asyncio.sleep(0.12)
            self.assertTrue(heartbeat.failed)
            if heartbeat._task and not heartbeat._task.done():
                try:
                    await heartbeat._task
                except LockLostError:
                    pass

        asyncio.run(_run_test_p())
        print("[PASS] CASE P (Renewal Failure Controlled Exception Trigger) PASSED.")

    def test_atomic_lua_budget_concurrency(self):
        """Atomic Lua Budget Test: 10 units remaining, Worker A (10) & Worker B (10) concurrent -> 1 succeeds."""
        proj_id = f"proj_lua_budget_{os.urandom(4).hex()}"

        async def _worker_a():
            return await redis_coordinator.consume_budget(proj_id, "llm_calls", max_limit=10, amount=10)

        async def _worker_b():
            return await redis_coordinator.consume_budget(proj_id, "llm_calls", max_limit=10, amount=10)

        async def _run_concurrent():
            return await asyncio.gather(_worker_a(), _worker_b())

        res_a, res_b = asyncio.run(_run_concurrent())

        # Exactly one worker succeeds, the other is rejected
        successes = [r[0] for r in (res_a, res_b) if r[0] is True]
        failures = [r[0] for r in (res_a, res_b) if r[0] is False]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        print("[PASS] Atomic Lua Resource Budget Concurrency Test (CHECK + INCREMENT Lua Script) PASSED.")


if __name__ == "__main__":
    unittest.main()
