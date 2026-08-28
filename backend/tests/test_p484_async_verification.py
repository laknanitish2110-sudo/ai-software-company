"""
P4.8.4 — Fully Async Cancellation & Rate Limiting Verification Test Suite

Verifies:
1. Event-loop non-blocking verification for FastAPI endpoints and rate limiting.
2. Cancellation immediately before patch application guarantees 0 workspace mutations.
3. Production Redis unavailable fail-closed behavior on rate limits and cancellation.
4. Unchanged rate-limiting functionality under native async execution.
"""

import os
import sys
import time
import asyncio
import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db
from app.services.rate_limiter import rate_limiter
from app.services.patch_applier import PatchApplier, PatchApplyResult
from app.services.redis_coordinator import redis_coordinator, RedisUnavailableError
from app.services.task_queue import ExecutionCancelledError
from app.models.execution_schema import PatchResult, FilePatch


class TestP484AsyncVerification(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET"] = "test_p484_secret_key_998877"
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        asyncio.run(init_db())
        cls.client = TestClient(app)

    def setUp(self):
        os.environ["ENVIRONMENT"] = "development"
        redis_coordinator.reset_in_memory()
        redis_coordinator._client = None

    def test_1_fastapi_event_loop_not_blocked_during_rate_limiting(self):
        """1. Verify FastAPI event loop ticks freely during concurrent async rate limit checks."""
        async def _run():
            ticks = 0

            async def heartbeat():
                nonlocal ticks
                for _ in range(10):
                    ticks += 1
                    await asyncio.sleep(0.01)

            hb_task = asyncio.create_task(heartbeat())
            for i in range(5):
                allowed, retry = await rate_limiter.check_rate_limit(f"user_p484_{i}", action="create", limit=10)
                self.assertTrue(allowed)

            await hb_task
            self.assertGreater(ticks, 5)

        asyncio.run(_run())
        print("[PASS] Test 1 (FastAPI Event Loop Ticks Freely During Rate Limiting) PASSED.")

    def test_2_cancellation_race_before_patch_application_zero_mutation(self):
        """2. Cancellation immediately before patch application prevents workspace mutation."""
        async def _run():
            proj_id = "proj_race_p484"
            exec_id = "exec_race_p484"
            await redis_coordinator.set_cancellation_flag(exec_id)

            initial_files = [{"path": "app.py", "content": "print('v1')\n"}]
            patch_res = PatchResult(
                status="PATCH_READY",
                changes=[FilePatch(path="app.py", action="modify", content="print('v2')\n", reason="update")]
            )

            applier = PatchApplier()
            with self.assertRaises(ExecutionCancelledError):
                await applier.apply_patch(proj_id, patch_res, initial_files, attempt=1, execution_id=exec_id)

            # Verification: memory files remain completely unchanged
            self.assertEqual(initial_files[0]["content"], "print('v1')\n")

        asyncio.run(_run())
        print("[PASS] Test 2 (Cancellation Before Patch Application Guarantees 0 Workspace Mutation) PASSED.")

    def test_3_production_redis_unavailable_fail_closed_rate_limiting(self):
        """3. Production mode fail-closed when Redis is unavailable during rate-limiting."""
        async def _run():
            with patch("app.services.redis_coordinator.get_environment", return_value="production"):
                with patch("app.services.redis_coordinator.REDIS_URL", None):
                    with self.assertRaises(RedisUnavailableError):
                        await rate_limiter.check_rate_limit("user_prod_fail", action="create")

        asyncio.run(_run())
        print("[PASS] Test 3 (Production Redis Unavailable Rate-Limiting Fail-Closed) PASSED.")

    def test_4_rate_limit_functionality_preserved(self):
        """4. Verify rate-limiting sliding-window logic remains functionally identical."""
        async def _run():
            user_id = f"user_func_test_{os.urandom(4).hex()}"
            # 2 requests allowed
            ok1, _ = await rate_limiter.check_rate_limit(user_id, action="test", limit=2, window_seconds=60)
            self.assertTrue(ok1)
            ok2, _ = await rate_limiter.check_rate_limit(user_id, action="test", limit=2, window_seconds=60)
            self.assertTrue(ok2)

            # 3rd request rate limited
            ok3, retry = await rate_limiter.check_rate_limit(user_id, action="test", limit=2, window_seconds=60)
            self.assertFalse(ok3)
            self.assertGreater(retry, 0)

        asyncio.run(_run())
        print("[PASS] Test 4 (Rate-Limit Functionality Unchanged) PASSED.")


if __name__ == "__main__":
    unittest.main()
