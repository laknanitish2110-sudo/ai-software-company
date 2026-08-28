"""
P4.8.1 — PostgreSQL Connection Lifecycle Focused Unit Test Suite

Verifies:
A. PostgreSQL connection is released back to pool after DBWrapper.close().
B. Calling close() twice does not trigger double-release.
C. SQLite connection closing behavior remains unchanged.
D. Exception paths and async context managers release connections.
E. Connection pool does not exhaust after repeated acquire/close cycles.
"""

import os
import sys
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.database import DBWrapper, get_db, _pg_pool


class MockAsyncConnection:
    def __init__(self):
        self.closed = False

    async def fetch(self, query, *args):
        return [{"id": "1", "status": "active"}]

    async def execute(self, query, *args):
        return "UPDATE 1"

    async def close(self):
        self.closed = True


class MockAsyncPool:
    def __init__(self, max_size=10):
        self.max_size = max_size
        self.acquired_count = 0
        self.released_count = 0
        self.active_connections = set()

    async def acquire(self):
        if len(self.active_connections) >= self.max_size:
            raise RuntimeError(f"Connection pool exhausted! Max limit: {self.max_size}")
        conn = MockAsyncConnection()
        self.active_connections.add(conn)
        self.acquired_count += 1
        return conn

    async def release(self, conn):
        if conn not in self.active_connections:
            raise RuntimeError("Attempted double-release or releasing connection not in active pool!")
        self.active_connections.remove(conn)
        self.released_count += 1


class TestP481PostgreSQLConnectionLifecycle(unittest.TestCase):

    def test_a_postgres_connection_released_after_close(self):
        """A. PostgreSQL connection is released back to pool after DBWrapper.close()."""
        async def _run():
            mock_pool = MockAsyncPool(max_size=10)
            with patch("app.core.database._pg_pool", mock_pool):
                conn = await mock_pool.acquire()
                wrapper = DBWrapper("postgres", conn)
                self.assertEqual(len(mock_pool.active_connections), 1)

                await wrapper.close()

                self.assertEqual(len(mock_pool.active_connections), 0)
                self.assertEqual(mock_pool.released_count, 1)
                self.assertIsNone(wrapper.conn)
                self.assertTrue(wrapper._closed)

        asyncio.run(_run())
        print("[PASS] Test A (PostgreSQL Connection Released After close()) PASSED.")

    def test_b_close_called_twice_no_double_release(self):
        """B. Calling close() twice does not trigger double-release."""
        async def _run():
            mock_pool = MockAsyncPool(max_size=10)
            with patch("app.core.database._pg_pool", mock_pool):
                conn = await mock_pool.acquire()
                wrapper = DBWrapper("postgres", conn)

                # First close call
                await wrapper.close()
                self.assertEqual(mock_pool.released_count, 1)

                # Second close call
                await wrapper.close()
                self.assertEqual(mock_pool.released_count, 1)
                self.assertIsNone(wrapper.conn)

        asyncio.run(_run())
        print("[PASS] Test B (Idempotent close() Prevents Double-Release) PASSED.")

    def test_c_sqlite_behavior_unchanged(self):
        """C. SQLite connection closing behavior remains unchanged."""
        async def _run():
            mock_sqlite_conn = AsyncMock()
            wrapper = DBWrapper("sqlite", mock_sqlite_conn)

            await wrapper.close()

            mock_sqlite_conn.close.assert_called_once()
            self.assertIsNone(wrapper.conn)
            self.assertTrue(wrapper._closed)

        asyncio.run(_run())
        print("[PASS] Test C (SQLite Behavior Unchanged) PASSED.")

    def test_d_exception_paths_and_context_manager_release(self):
        """D. Exception paths and async context managers release connections."""
        async def _run():
            mock_pool = MockAsyncPool(max_size=10)
            with patch("app.core.database._pg_pool", mock_pool):
                conn = await mock_pool.acquire()
                wrapper = DBWrapper("postgres", conn)

                try:
                    async with wrapper as db:
                        self.assertEqual(len(mock_pool.active_connections), 1)
                        raise ValueError("Simulated operational failure inside query block")
                except ValueError:
                    pass

                self.assertEqual(len(mock_pool.active_connections), 0)
                self.assertEqual(mock_pool.released_count, 1)
                self.assertTrue(wrapper._closed)

        asyncio.run(_run())
        print("[PASS] Test D (Async Context Manager Exception Release) PASSED.")

    def test_e_pool_does_not_exhaust_after_50_cycles(self):
        """E. Connection pool does not exhaust after repeated 50 acquire/close cycles."""
        async def _run():
            mock_pool = MockAsyncPool(max_size=10)
            with patch("app.core.database._pg_pool", mock_pool):
                for i in range(50):
                    conn = await mock_pool.acquire()
                    wrapper = DBWrapper("postgres", conn)
                    res = await wrapper.execute("SELECT 1")
                    rows = await res.fetchall()
                    self.assertEqual(len(rows), 1)
                    await wrapper.close()

                self.assertEqual(mock_pool.acquired_count, 50)
                self.assertEqual(mock_pool.released_count, 50)
                self.assertEqual(len(mock_pool.active_connections), 0)

        asyncio.run(_run())
        print("[PASS] Test E (50 Sequential Acquire/Close Cycles Without Pool Exhaustion) PASSED.")


if __name__ == "__main__":
    unittest.main()
