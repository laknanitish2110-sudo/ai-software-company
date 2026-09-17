"""
P4.8.4 — PostgreSQL Dialect & Persistence Hardening Tests

Tests for:
1. _to_pg_sql INSERT OR IGNORE → INSERT INTO ... ON CONFLICT DO NOTHING translation
2. _to_pg_sql bare ON CONFLICT DO NOTHING passthrough (no hardcoded column rewrite)
3. delete_project cleans up execution_events table
4. force_release_lock bypasses token verification
"""

import asyncio
import unittest
import os
import sys

# Ensure ENVIRONMENT is not production for tests
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_p484")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import DBWrapper, get_db, init_db, create_project, delete_project, save_execution_event, get_execution_events_since, create_user
from app.services.redis_coordinator import redis_coordinator, InMemoryCoordinator


class TestToPgSqlTranslation(unittest.TestCase):
    """Tests for _to_pg_sql dialect translation correctness."""

    def setUp(self):
        self.wrapper = DBWrapper("postgres", None)

    def test_insert_or_ignore_translated(self):
        """INSERT OR IGNORE INTO should become INSERT INTO ... ON CONFLICT DO NOTHING."""
        sql = "INSERT OR IGNORE INTO agent_outputs (id, project_id, role) VALUES (?, ?, ?)"
        result = self.wrapper._to_pg_sql(sql)
        self.assertNotIn("INSERT OR IGNORE", result)
        self.assertIn("INSERT INTO", result)
        self.assertIn("ON CONFLICT DO NOTHING", result)
        self.assertIn("$1", result)
        self.assertIn("$2", result)
        self.assertIn("$3", result)

    def test_insert_or_ignore_no_duplicate_on_conflict(self):
        """INSERT OR IGNORE with existing ON CONFLICT should not add another ON CONFLICT."""
        sql = "INSERT OR IGNORE INTO t (id) VALUES (?) ON CONFLICT (id) DO NOTHING"
        result = self.wrapper._to_pg_sql(sql)
        self.assertNotIn("INSERT OR IGNORE", result)
        # Should not have two ON CONFLICT clauses
        count = result.count("ON CONFLICT")
        self.assertEqual(count, 1)

    def test_bare_on_conflict_do_nothing_not_rewritten(self):
        """Bare ON CONFLICT DO NOTHING should NOT be rewritten to add (project_id, agent_role)."""
        sql = "INSERT INTO conversations (id, project_id, agent_role, messages, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING"
        result = self.wrapper._to_pg_sql(sql)
        # Must NOT contain hardcoded column target
        self.assertNotIn("ON CONFLICT (project_id, agent_role)", result)
        # Must contain bare ON CONFLICT DO NOTHING
        self.assertIn("ON CONFLICT DO NOTHING", result)

    def test_targeted_on_conflict_preserved(self):
        """ON CONFLICT (project_id, seq) DO NOTHING should pass through untouched."""
        sql = "INSERT INTO execution_events (id, project_id, seq) VALUES (?, ?, ?) ON CONFLICT (project_id, seq) DO NOTHING"
        result = self.wrapper._to_pg_sql(sql)
        self.assertIn("ON CONFLICT (project_id, seq) DO NOTHING", result)

    def test_placeholder_conversion(self):
        """? placeholders should become $N positional params."""
        sql = "SELECT * FROM users WHERE email = ? AND id = ?"
        result = self.wrapper._to_pg_sql(sql)
        self.assertIn("$1", result)
        self.assertIn("$2", result)
        self.assertNotIn("?", result)

    def test_normal_insert_unchanged(self):
        """Normal INSERT without OR IGNORE or ON CONFLICT should not be altered beyond placeholder conversion."""
        sql = "INSERT INTO projects (id, problem_statement) VALUES (?, ?)"
        result = self.wrapper._to_pg_sql(sql)
        self.assertEqual(result, "INSERT INTO projects (id, problem_statement) VALUES ($1, $2)")


class TestDeleteProjectCleansEvents(unittest.TestCase):
    """Tests that delete_project removes execution_events rows."""

    def test_delete_project_removes_execution_events(self):
        async def _run():
            await init_db()
            # Create user and project
            user = await create_user(f"test_p484_del_{os.urandom(4).hex()}@test.com", "hash")
            user_id = user["id"]
            from app.core.database import create_project as cp
            project = await cp("Test problem for deletion", user_id=user_id)
            pid = project["id"]

            # Save an execution event
            await save_execution_event(pid, "exec_test123", 1, "test_event", {"key": "value"})

            # Verify event exists
            events = await get_execution_events_since(pid, last_seq=0)
            self.assertGreaterEqual(len(events), 1)

            # Delete project
            deleted = await delete_project(pid, user_id)
            self.assertTrue(deleted)

            # Verify events are gone
            events_after = await get_execution_events_since(pid, last_seq=0)
            self.assertEqual(len(events_after), 0)

        asyncio.run(_run())


class TestForceReleaseLock(unittest.TestCase):
    """Tests for force_release_lock bypassing token verification."""

    def test_force_release_lock_inmemory(self):
        async def _run():
            coord = InMemoryCoordinator()
            # Acquire a lock
            token = await coord.acquire_lock("proj_force_test", ttl_seconds=60)
            self.assertIsNotNone(token)

            # Normal release with wrong token should fail
            released = await coord.release_lock("proj_force_test", "wrong_token")
            self.assertFalse(released)

            # Lock should still be held
            token2 = await coord.acquire_lock("proj_force_test", ttl_seconds=60)
            self.assertIsNone(token2)  # Still locked

            # Force release should succeed without token
            force_released = await coord.force_release_lock("proj_force_test")
            self.assertTrue(force_released)

            # Lock should now be available
            token3 = await coord.acquire_lock("proj_force_test", ttl_seconds=60)
            self.assertIsNotNone(token3)

        asyncio.run(_run())

    def test_force_release_nonexistent_lock(self):
        async def _run():
            coord = InMemoryCoordinator()
            # Force release on non-existent lock should return False
            result = await coord.force_release_lock("nonexistent_project")
            self.assertFalse(result)

        asyncio.run(_run())

    def test_redis_coordinator_force_release_fallback(self):
        """RedisCoordinator.force_release_lock should work via in-memory fallback in dev."""
        async def _run():
            redis_coordinator.reset_in_memory()
            # Acquire via coordinator (will use in-memory fallback in dev)
            token = await redis_coordinator.acquire_lock("proj_rc_force", ttl_seconds=60)
            self.assertIsNotNone(token)

            # Force release via coordinator
            released = await redis_coordinator.force_release_lock("proj_rc_force")
            self.assertTrue(released)

            # Should be re-acquirable
            token2 = await redis_coordinator.acquire_lock("proj_rc_force", ttl_seconds=60)
            self.assertIsNotNone(token2)

            redis_coordinator.reset_in_memory()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
