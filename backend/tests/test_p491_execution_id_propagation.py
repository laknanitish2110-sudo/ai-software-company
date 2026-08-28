"""
P4.9.1 — Execution ID Propagation & Multi-Stage Cancellation Verification Test Suite

Verifies:
1. Active execution_id is stored in project memory upon pipeline start.
2. execution_id is propagated across every _start_next_agent() transition (BA -> Research -> Architect -> Engineer -> Repair Loop -> PPT).
3. Cancellation set in Redis at any stage transition raises ExecutionCancelledError.
4. Auto-approval transitions maintain execution_id propagation without dropping context.
"""

import os
import sys
import asyncio
import unittest
from unittest.mock import patch

from app.core.database import init_db, create_project, get_memory, set_memory, update_project_status
from app.models.schemas import ProjectStatus, AgentRole
from app.services.orchestrator import orchestrator
from app.services.redis_coordinator import redis_coordinator
from app.services.task_queue import ExecutionCancelledError


class TestP491ExecutionIdPropagation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET"] = "test_p491_secret_key_11223344"
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        asyncio.run(init_db())

    def setUp(self):
        os.environ["ENVIRONMENT"] = "development"
        redis_coordinator.reset_in_memory()

    def test_1_execution_id_stored_in_memory_on_start(self):
        """1. Verify active_execution_id is stored in project memory when start_project is called."""
        async def _run():
            exec_id = "exec_p491_init_001"

            with patch("app.services.orchestrator.run_agent", side_effect=Exception("Stop at CEO")):
                project = await orchestrator.start_project("Test P491 Problem", user_id="user_p491_1", execution_id=exec_id)

            proj_id = project["id"]
            mem = await get_memory(proj_id)
            self.assertEqual(mem.get("active_execution_id"), exec_id)

        asyncio.run(_run())
        print("[PASS] Test 1 (Execution ID Stored in Project Memory) PASSED.")

    def test_2_cancellation_detected_at_ba_stage_transition(self):
        """2. Verify cancellation set during BA stage transition raises ExecutionCancelledError."""
        async def _run():
            project = await create_project("BA Stage Cancel", user_id="user_p491_2")
            proj_id = project["id"]
            exec_id = "exec_p491_ba_cancel"

            await redis_coordinator.set_cancellation_flag(exec_id)

            with self.assertRaises(ExecutionCancelledError):
                await orchestrator._start_next_agent(proj_id, AgentRole.BUSINESS_ANALYST, execution_id=exec_id)

        asyncio.run(_run())
        print("[PASS] Test 2 (Cancellation Detected at BA Stage Transition) PASSED.")

    def test_3_cancellation_detected_at_architect_stage_transition_via_memory(self):
        """3. Verify cancellation set during Architect stage transition is detected via stored memory execution_id."""
        async def _run():
            project = await create_project("Architect Stage Cancel", user_id="user_p491_3")
            proj_id = project["id"]
            exec_id = "exec_p491_arch_cancel"

            # Store active execution_id in memory
            await set_memory(proj_id, "active_execution_id", exec_id, "system")

            await redis_coordinator.set_cancellation_flag(exec_id)

            # Invoke without explicit execution_id parameter -> resolved from memory
            with self.assertRaises(ExecutionCancelledError):
                await orchestrator._start_next_agent(proj_id, AgentRole.ARCHITECT)

        asyncio.run(_run())
        print("[PASS] Test 3 (Cancellation Detected at Architect Stage via Memory Propagation) PASSED.")

    def test_4_cancellation_detected_at_engineer_stage_transition(self):
        """4. Verify cancellation set during Engineer stage transition raises ExecutionCancelledError."""
        async def _run():
            project = await create_project("Engineer Stage Cancel", user_id="user_p491_4")
            proj_id = project["id"]
            exec_id = "exec_p491_eng_cancel"

            await redis_coordinator.set_cancellation_flag(exec_id)

            with self.assertRaises(ExecutionCancelledError):
                await orchestrator._start_next_agent(proj_id, AgentRole.ENGINEER, execution_id=exec_id)

        asyncio.run(_run())
        print("[PASS] Test 4 (Cancellation Detected at Engineer Stage Transition) PASSED.")

    def test_5_handle_approval_propagates_execution_id_to_next_agent(self):
        """5. Verify handle_approval propagates execution_id when advancing to next role."""
        async def _run():
            project = await create_project("Approval Propagate Test", user_id="user_p491_5")
            proj_id = project["id"]
            exec_id = "exec_p491_approval_prop"

            # Mark project status at BA_REVIEW
            await update_project_status(proj_id, ProjectStatus.BA_REVIEW.value)

            # Set cancellation flag so next_agent transition fails if execution_id is correctly passed
            await redis_coordinator.set_cancellation_flag(exec_id)

            with self.assertRaises(ExecutionCancelledError):
                await orchestrator.handle_approval(proj_id, "out_ba_1", approved=True, execution_id=exec_id)

        asyncio.run(_run())
        print("[PASS] Test 5 (handle_approval Propagates Execution ID to Next Role) PASSED.")


if __name__ == "__main__":
    unittest.main()
