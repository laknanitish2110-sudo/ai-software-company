"""
P4.9.2 — Redis Cancellation Sync-Fallback Hardening Focused Unit Test Suite

Verifies:
1. Synchronous cancellation evaluation on an active event loop in production raises RedisUnavailableError fail-closed without blocking the event loop thread for 5 seconds.
2. Synchronous rate limit evaluation on an active event loop in production raises RedisUnavailableError fail-closed without blocking the event loop thread.
3. Development mode synchronous fallback on an active event loop returns in-memory fallback immediately.
4. Async await redis_coordinator.is_cancelled(...) continues to evaluate cleanly and non-blockingly.
"""

import os
import sys
import time
import asyncio
import unittest
from unittest.mock import patch

from app.services.redis_coordinator import redis_coordinator, RedisUnavailableError


class TestP492SyncRedisHardening(unittest.TestCase):

    def setUp(self):
        os.environ["ENVIRONMENT"] = "development"
        redis_coordinator.reset_in_memory()

    def test_1_sync_cancellation_on_running_loop_in_production_fails_closed_without_blocking(self):
        """1. Verify sync _is_cancelled_sync on a running loop in production fails closed immediately without 5s deadlock."""
        async def _run():
            start_time = time.time()
            with patch("app.services.redis_coordinator.get_environment", return_value="production"):
                with patch("app.services.redis_coordinator.REDIS_URL", "redis://localhost:6379/0"):
                    with patch.object(redis_coordinator, "_client", new="mock_redis_client"):
                        with self.assertRaises(RedisUnavailableError):
                            # This calls _is_cancelled_sync under the hood via __bool__
                            bool(redis_coordinator.is_cancelled("exec_p492_test_1"))
            elapsed = time.time() - start_time
            # Must fail closed immediately (< 0.1s), NOT block for 5.0s
            self.assertLess(elapsed, 0.5)

        asyncio.run(_run())
        print("[PASS] Test 1 (Production Sync Cancellation on Running Loop Fails Closed Without Deadlock) PASSED.")

    def test_2_sync_rate_limit_on_running_loop_in_production_fails_closed_without_blocking(self):
        """2. Verify sync check_rate_limit on a running loop in production fails closed immediately."""
        async def _run():
            start_time = time.time()
            with patch("app.services.redis_coordinator.get_environment", return_value="production"):
                with patch("app.services.redis_coordinator.REDIS_URL", "redis://localhost:6379/0"):
                    with patch.object(redis_coordinator, "_client", new="mock_redis_client"):
                        with self.assertRaises(RedisUnavailableError):
                            redis_coordinator.check_rate_limit("user_p492_2", action="run")
            elapsed = time.time() - start_time
            self.assertLess(elapsed, 0.5)

        asyncio.run(_run())
        print("[PASS] Test 2 (Production Sync Rate Limit on Running Loop Fails Closed Without Deadlock) PASSED.")

    def test_3_development_mode_sync_fallback_on_running_loop_returns_in_memory_result(self):
        """3. Verify development mode sync fallback on a running loop uses in-memory fallback."""
        async def _run():
            exec_id = "exec_p492_dev_3"
            await redis_coordinator.set_cancellation_flag(exec_id)

            with patch("app.services.redis_coordinator.get_environment", return_value="development"):
                self.assertTrue(bool(redis_coordinator.is_cancelled(exec_id)))

        asyncio.run(_run())
        print("[PASS] Test 3 (Development Mode Sync Fallback Preserved) PASSED.")

    def test_4_async_cancellation_evaluation_unaffected_and_non_blocking(self):
        """4. Verify async await redis_coordinator.is_cancelled(...) evaluates asynchronously without blocking."""
        async def _run():
            exec_id = "exec_p492_async_4"
            await redis_coordinator.set_cancellation_flag(exec_id)

            cancelled = await redis_coordinator.is_cancelled(exec_id)
            self.assertTrue(cancelled)

        asyncio.run(_run())
        print("[PASS] Test 4 (Async Cancellation Evaluation Unaffected) PASSED.")


if __name__ == "__main__":
    unittest.main()
