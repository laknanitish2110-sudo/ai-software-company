import asyncio
import unittest
from unittest.mock import patch, AsyncMock
import os

# Set test environment
os.environ["ENVIRONMENT"] = "development"

from app.services.orchestrator import orchestrator
from app.core.database import (
    init_db,
    create_project,
    save_agent_output,
    update_output_status_atomic,
    get_db,
)


class TestP482ApprovalIdempotency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asyncio.run(init_db())

    def test_cross_project_isolation_and_atomic_transitions(self):
        """Database direct test for update_output_status_atomic project isolation and transition semantics."""
        async def _test():
            proj_a = await create_project("Project A", user_id="user_a")
            proj_a_id = proj_a["id"]

            proj_b = await create_project("Project B", user_id="user_b")
            proj_b_id = proj_b["id"]

            out_a = await save_agent_output(proj_a_id, "business_analyst", {"data": "A"})
            out_a_id = out_a["id"]

            out_b = await save_agent_output(proj_b_id, "business_analyst", {"data": "B"})
            out_b_id = out_b["id"]

            # 1. Attempting to approve Output B using Project A's ID must return False
            res_cross_approve = await update_output_status_atomic(out_b_id, proj_a_id, "approved", "pending")
            self.assertFalse(res_cross_approve)

            # Verify Output B remains pending
            db = await get_db()
            try:
                cur = await db.execute("SELECT status FROM agent_outputs WHERE id = ?", (out_b_id,))
                row = await cur.fetchone()
                self.assertEqual(row["status"], "pending")
            finally:
                await db.close()

            # 2. Attempting to reject Output B using Project A's ID must return False
            res_cross_reject = await update_output_status_atomic(out_b_id, proj_a_id, "rejected", "pending")
            self.assertFalse(res_cross_reject)

            # Verify Output B remains pending
            db = await get_db()
            try:
                cur = await db.execute("SELECT status FROM agent_outputs WHERE id = ?", (out_b_id,))
                row = await cur.fetchone()
                self.assertEqual(row["status"], "pending")
            finally:
                await db.close()

            # Inverse: Attempting to approve Output A using Project B's ID must return False
            res_inv_approve = await update_output_status_atomic(out_a_id, proj_b_id, "approved", "pending")
            self.assertFalse(res_inv_approve)

            # Inverse: Attempting to reject Output A using Project B's ID must return False
            res_inv_reject = await update_output_status_atomic(out_a_id, proj_b_id, "rejected", "pending")
            self.assertFalse(res_inv_reject)

            # Verify Output A remains pending
            db = await get_db()
            try:
                cur = await db.execute("SELECT status FROM agent_outputs WHERE id = ?", (out_a_id,))
                row = await cur.fetchone()
                self.assertEqual(row["status"], "pending")
            finally:
                await db.close()

            # 3. Correct project + pending output transitions successfully
            res_correct = await update_output_status_atomic(out_a_id, proj_a_id, "approved", "pending")
            self.assertTrue(res_correct)

            # 4. Correct project + duplicate transition remains False
            res_dup = await update_output_status_atomic(out_a_id, proj_a_id, "approved", "pending")
            self.assertFalse(res_dup)

            # Missing output -> False
            res_missing = await update_output_status_atomic("nonexistent_id", proj_a_id, "approved", "pending")
            self.assertFalse(res_missing)

        asyncio.run(_test())

    def test_1_single_approval(self):
        """TEST 1 — Single approval transitions output and triggers exactly one downstream transition."""
        async def _test():
            proj = await create_project("Single Approval Test", user_id="test_user")
            proj_id = proj["id"]

            db = await get_db()
            try:
                await db.execute("UPDATE projects SET status = 'ba_review' WHERE id = ?", (proj_id,))
                await db.commit()
            finally:
                await db.close()

            out = await save_agent_output(proj_id, "business_analyst", {"data": "test"})
            out_id = out["id"]

            start_next_mock = AsyncMock()
            with patch.object(orchestrator, "_start_next_agent", new=start_next_mock):
                await orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1")

            start_next_mock.assert_called_once()

            db = await get_db()
            try:
                cursor = await db.execute("SELECT status FROM agent_outputs WHERE id = ?", (out_id,))
                row = await cursor.fetchone()
                self.assertEqual(row["status"], "approved")
            finally:
                await db.close()

        asyncio.run(_test())

    def test_2_duplicate_sequential_approval(self):
        """TEST 2 — Duplicate sequential approval triggers downstream agent exactly once."""
        async def _test():
            proj = await create_project("Sequential Approval Test", user_id="test_user")
            proj_id = proj["id"]

            db = await get_db()
            try:
                await db.execute("UPDATE projects SET status = 'ba_review' WHERE id = ?", (proj_id,))
                await db.commit()
            finally:
                await db.close()

            out = await save_agent_output(proj_id, "business_analyst", {"data": "test"})
            out_id = out["id"]

            start_next_mock = AsyncMock()
            with patch.object(orchestrator, "_start_next_agent", new=start_next_mock):
                await orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1")
                await orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1")

            start_next_mock.assert_called_once()

        asyncio.run(_test())

    def test_3_concurrent_approvals(self):
        """TEST 3 — 5 concurrent approvals trigger downstream agent exactly once."""
        async def _test():
            proj = await create_project("Concurrent Approvals Test", user_id="test_user")
            proj_id = proj["id"]

            db = await get_db()
            try:
                await db.execute("UPDATE projects SET status = 'ba_review' WHERE id = ?", (proj_id,))
                await db.commit()
            finally:
                await db.close()

            out = await save_agent_output(proj_id, "business_analyst", {"data": "test"})
            out_id = out["id"]

            start_next_mock = AsyncMock()
            with patch.object(orchestrator, "_start_next_agent", new=start_next_mock):
                await asyncio.gather(
                    orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1"),
                    orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1"),
                    orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1"),
                    orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1"),
                    orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1"),
                )

            start_next_mock.assert_called_once()

            db = await get_db()
            try:
                cursor = await db.execute("SELECT status FROM agent_outputs WHERE id = ?", (out_id,))
                row = await cursor.fetchone()
                self.assertEqual(row["status"], "approved")
            finally:
                await db.close()

        asyncio.run(_test())

    def test_4_approval_rejection_race(self):
        """TEST 4 — Approval then rejection race executes exactly one downstream path."""
        async def _test():
            proj = await create_project("Race Test", user_id="test_user")
            proj_id = proj["id"]

            db = await get_db()
            try:
                await db.execute("UPDATE projects SET status = 'ba_review' WHERE id = ?", (proj_id,))
                await db.commit()
            finally:
                await db.close()

            out = await save_agent_output(proj_id, "business_analyst", {"data": "test"})
            out_id = out["id"]

            start_next_mock = AsyncMock()

            with patch.object(orchestrator, "_start_next_agent", new=start_next_mock):
                await asyncio.gather(
                    orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1"),
                    orchestrator.handle_approval(proj_id, out_id, False, feedback="Fix this", execution_id="exec1"),
                )

            start_next_mock.assert_called_once()

            db = await get_db()
            try:
                cursor = await db.execute("SELECT status FROM agent_outputs WHERE id = ?", (out_id,))
                row = await cursor.fetchone()
                self.assertIn(row["status"], ["approved", "rejected"])
            finally:
                await db.close()

        asyncio.run(_test())

    def test_5_duplicate_rejection(self):
        """TEST 5 — Duplicate rejection executes revision path only once."""
        async def _test():
            proj = await create_project("Duplicate Rejection Test", user_id="test_user")
            proj_id = proj["id"]

            db = await get_db()
            try:
                await db.execute("UPDATE projects SET status = 'ba_review' WHERE id = ?", (proj_id,))
                await db.commit()
            finally:
                await db.close()

            out = await save_agent_output(proj_id, "business_analyst", {"data": "test"})
            out_id = out["id"]

            start_next_mock = AsyncMock()
            with patch.object(orchestrator, "_start_next_agent", new=start_next_mock):
                await orchestrator.handle_approval(proj_id, out_id, False, feedback="Revise", execution_id="exec1")
                await orchestrator.handle_approval(proj_id, out_id, False, feedback="Revise again", execution_id="exec1")

            start_next_mock.assert_called_once()

        asyncio.run(_test())

    def test_6_stale_already_approved_output(self):
        """TEST 6 — Calling handle_approval on already-approved output performs no downstream work."""
        async def _test():
            proj = await create_project("Stale Approved Test", user_id="test_user")
            proj_id = proj["id"]

            out = await save_agent_output(proj_id, "business_analyst", {"data": "test"})
            out_id = out["id"]

            db = await get_db()
            try:
                await db.execute("UPDATE agent_outputs SET status = 'approved' WHERE id = ?", (out_id,))
                await db.commit()
            finally:
                await db.close()

            start_next_mock = AsyncMock()
            with patch.object(orchestrator, "_start_next_agent", new=start_next_mock):
                await orchestrator.handle_approval(proj_id, out_id, True, execution_id="exec1")

            start_next_mock.assert_not_called()

        asyncio.run(_test())

    def test_7_stale_already_rejected_output(self):
        """TEST 7 — Calling handle_approval on already-rejected output performs no downstream work."""
        async def _test():
            proj = await create_project("Stale Rejected Test", user_id="test_user")
            proj_id = proj["id"]

            out = await save_agent_output(proj_id, "business_analyst", {"data": "test"})
            out_id = out["id"]

            db = await get_db()
            try:
                await db.execute("UPDATE agent_outputs SET status = 'rejected' WHERE id = ?", (out_id,))
                await db.commit()
            finally:
                await db.close()

            start_next_mock = AsyncMock()
            with patch.object(orchestrator, "_start_next_agent", new=start_next_mock):
                await orchestrator.handle_approval(proj_id, out_id, False, feedback="Fix", execution_id="exec1")

            start_next_mock.assert_not_called()

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
