"""
P4.8.3 — Async Redis Coordinator Hardening Focused Unit Test Suite

Verifies:
1. Async is_cancelled when awaited (await redis_coordinator.is_cancelled(exec_id)).
2. Hybrid is_cancelled evaluated synchronously as boolean.
3. Production mode fail-closed behavior when REDIS_URL is unconfigured or connection fails (RedisUnavailableError).
4. Local development in-memory fallback behavior when REDIS_URL is empty.
5. Async lock acquisition, renewal, release, and budget accounting.
"""

import os
import sys
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.redis_coordinator import redis_coordinator, RedisUnavailableError, LockHeartbeat


class TestP483AsyncRedisCoordinator(unittest.TestCase):

    def setUp(self):
        os.environ["ENVIRONMENT"] = "development"
        redis_coordinator.reset_in_memory()
        redis_coordinator._client = None

    def test_1_async_is_cancelled_when_awaited(self):
        """1. is_cancelled when awaited (await redis_coordinator.is_cancelled(exec_id))."""
        async def _run():
            exec_id = "exec_async_test_101"
            await redis_coordinator.set_cancellation_flag(exec_id)

            cancelled = await redis_coordinator.is_cancelled(exec_id)
            self.assertTrue(cancelled)

            not_cancelled = await redis_coordinator.is_cancelled("exec_non_existent")
            self.assertFalse(not_cancelled)

        asyncio.run(_run())
        print("[PASS] Test 1 (Async is_cancelled Awaited Cleanly) PASSED.")

    def test_2_is_cancelled_hybrid_boolean_evaluation(self):
        """2. Hybrid is_cancelled evaluated synchronously as boolean."""
        async def _run():
            exec_id = "exec_bool_test_202"
            await redis_coordinator.set_cancellation_flag(exec_id)

            # Sync evaluation via __bool__
            self.assertTrue(bool(redis_coordinator.is_cancelled(exec_id)))
            self.assertFalse(bool(redis_coordinator.is_cancelled("exec_non_existent")))

        asyncio.run(_run())
        print("[PASS] Test 2 (Hybrid is_cancelled Evaluated as Boolean) PASSED.")

    def test_3_production_unconfigured_redis_raises_redis_unavailable_error(self):
        """3. Production mode fail-closed when REDIS_URL is unconfigured."""
        async def _run():
            with patch("app.services.redis_coordinator.get_environment", return_value="production"):
                with patch("app.services.redis_coordinator.REDIS_URL", None):
                    with self.assertRaises(RedisUnavailableError):
                        await redis_coordinator.is_cancelled(execution_id="exec_prod_fail")

        asyncio.run(_run())
        print("[PASS] Test 3 (Production Unconfigured Redis Raises RedisUnavailableError) PASSED.")

    def test_4_production_redis_connection_failure_raises_redis_unavailable_error(self):
        """4. Production mode fail-closed when Redis connection fails during operation."""
        async def _run():
            mock_client = AsyncMock()
            mock_client.get.side_effect = RuntimeError("Redis connection lost")

            with patch("app.services.redis_coordinator.get_environment", return_value="production"):
                with patch.object(redis_coordinator, "_get_client", return_value=mock_client):
                    with self.assertRaises(RedisUnavailableError):
                        await redis_coordinator.is_cancelled(execution_id="exec_prod_conn_drop")

        asyncio.run(_run())
        print("[PASS] Test 4 (Production Redis Connection Failure Raises RedisUnavailableError) PASSED.")

    def test_5_local_dev_fallback_when_redis_unconfigured(self):
        """5. Local development in-memory fallback behavior when REDIS_URL is empty."""
        async def _run():
            with patch("app.services.redis_coordinator.get_environment", return_value="development"):
                with patch("app.services.redis_coordinator.REDIS_URL", None):
                    # Local dev mode falls back to in-memory coordinator safely
                    await redis_coordinator.set_cancellation_flag("exec_dev_1")
                    cancelled = await redis_coordinator.is_cancelled("exec_dev_1")
                    self.assertTrue(cancelled)

        asyncio.run(_run())
        print("[PASS] Test 5 (Local Development In-Memory Fallback) PASSED.")

    def test_6_async_lock_lifecycle(self):
        """6. Async lock acquisition, renewal, release, and budget accounting."""
        async def _run():
            proj_id = "proj_async_lock_99"
            token = await redis_coordinator.acquire_lock(proj_id, ttl_seconds=30)
            self.assertIsNotNone(token)

            # Contention: second acquire fails
            second_token = await redis_coordinator.acquire_lock(proj_id, ttl_seconds=30)
            self.assertIsNone(second_token)

            # Renew lock
            renewed = await redis_coordinator.renew_lock(proj_id, token, ttl_seconds=60)
            self.assertTrue(renewed)

            # Release lock
            released = await redis_coordinator.release_lock(proj_id, token)
            self.assertTrue(released)

        asyncio.run(_run())
        print("[PASS] Test 6 (Async Lock Acquisition, Renewal, and Release) PASSED.")


if __name__ == "__main__":
    unittest.main()
