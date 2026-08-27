import os
import sys
import shutil
import asyncio
import unittest

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.execution_schema import (
    DefinitionOfDone,
    DoDItem,
    ExecutionPlan,
    ExecutionCommands,
    PatchResult,
    FilePatch
)
from app.services.sandbox_runner import (
    LocalSubprocessSandboxRunner,
    E2BSandboxRunner,
    ExecutionResult
)
from app.agents.qa import evaluate_qa_results, QAReport
from app.services.repair_context_builder import build_repair_context
from app.agents.fixer import validate_patch
from app.services.patch_applier import PatchApplier, PROJECTS_DIR


class TestP23RepairCycle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"

    def setUp(self):
        self.test_pid = "test_p23_repair_pid_99"
        self.project_dir = PROJECTS_DIR / self.test_pid
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir, ignore_errors=True)
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir, ignore_errors=True)

    def test_1_deterministic_single_repair_cycle(self):
        """Test 1: Full single repair cycle (Attempt 1 FAIL -> Fixer -> Patch -> Attempt 2 PASS)."""
        # Initial broken project files
        initial_files = [
            {"path": "requirements.txt", "content": ""},
            {"path": "src/math_utils.py", "content": "def add(a, b):\n    return a - b  # BUG: subtraction instead of addition\n"},
            {"path": "test_math.py", "content": "from src.math_utils import add\nassert add(2, 3) == 5, 'add(2, 3) should equal 5'\nprint('PASS')\n"}
        ]

        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands=ExecutionCommands(
                install="python --version",
                build="python -m py_compile src/math_utils.py",
                test="python test_math.py"
            )
        )

        dod = DefinitionOfDone(items=[
            DoDItem(id="AC-BUILD", description="Build cleanly", verification_type="build"),
            DoDItem(id="AC-TEST", description="Unit tests pass", verification_type="test")
        ])

        runner = LocalSubprocessSandboxRunner()

        # Step 1: Attempt 1 execution -> Expected FAIL
        res1: ExecutionResult = asyncio.run(runner.execute(self.test_pid, initial_files, plan))
        self.assertEqual(res1.overall_status, "FAILED")
        self.assertEqual(res1.failed_stage, "TEST")

        qa1: QAReport = evaluate_qa_results(dod, res1)
        self.assertEqual(qa1.status, "FAIL")
        self.assertEqual(qa1.failure_category, "TEST_FAILURE")

        # Step 2: Build RepairContext and Fixer Patch
        repair_ctx = build_repair_context(self.test_pid, qa1, res1, dod, engineer_output={"files": initial_files})
        
        # Fixer generates targeted patch fixing the bug
        patch_res = PatchResult(
            status="PATCH_READY",
            changes=[
                FilePatch(
                    path="src/math_utils.py",
                    action="modify",
                    content="def add(a, b):\n    return a + b  # FIXED\n",
                    reason="Fix subtraction bug in add function"
                )
            ]
        )

        validated_patch = validate_patch(patch_res, repair_ctx)
        self.assertEqual(validated_patch.status, "PATCH_READY")

        # Step 3: Apply patch via PatchApplier
        applier = PatchApplier()
        snapshot = applier.create_snapshot(self.test_pid, initial_files)
        apply_res, patched_files = applier.apply_patch(self.test_pid, validated_patch, initial_files, attempt=1)

        self.assertEqual(apply_res.status, "APPLIED")
        self.assertEqual(apply_res.modified_files, ["src/math_utils.py"])

        # Step 4: Attempt 2 execution -> Expected PASS
        res2: ExecutionResult = asyncio.run(runner.execute(self.test_pid, patched_files, plan))
        self.assertEqual(res2.overall_status, "PASSED")

        qa2: QAReport = evaluate_qa_results(dod, res2)
        self.assertEqual(qa2.status, "PASS")
        self.assertEqual(qa2.failure_category, "NONE")

        print("[PASS] Test 1: Deterministic Single Repair Cycle PASSED.")

    def test_2_rollback_and_invalid_patch_atomicity(self):
        """Test 2: Invalid patch rejection, atomicity (0 files modified), and snapshot rollback."""
        initial_files = [
            {"path": "src/app.py", "content": "print('Original Valid Code')\n"}
        ]

        applier = PatchApplier()
        snapshot = applier.create_snapshot(self.test_pid, initial_files)

        # Create invalid patch attempting path traversal
        invalid_patch = PatchResult(
            status="PATCH_READY",
            changes=[
                FilePatch(path="src/app.py", action="modify", content="valid part"),
                FilePatch(path="../secret.txt", action="modify", content="traversal attempt")
            ]
        )

        apply_res, updated_memory = applier.apply_patch(self.test_pid, invalid_patch, initial_files, attempt=1)

        self.assertEqual(apply_res.status, "REJECTED")
        self.assertGreater(len(apply_res.errors), 0)
        self.assertIn("Path traversal", apply_res.errors[0])
        # Atomicity check: memory files remain unchanged
        self.assertEqual(updated_memory[0]["content"], "print('Original Valid Code')\n")

        # Test snapshot rollback
        rollbacked_memory = applier.rollback_snapshot(self.test_pid, snapshot, updated_memory)
        self.assertEqual(rollbacked_memory[0]["content"], "print('Original Valid Code')\n")

        print("[PASS] Test 2: Rollback and Invalid Patch Atomicity PASSED.")

    def test_3_real_e2b_cloud_re_execution_repair_cycle(self):
        """Test 3: Real AWS Firecracker E2B Cloud Sandbox Re-Execution Repair Cycle."""
        api_key = os.getenv("E2B_API_KEY", "")
        if not api_key:
            print("[SKIP] Test 3: E2B_API_KEY unavailable for live E2B repair cycle test.")
            return

        initial_files = [
            {"path": "requirements.txt", "content": ""},
            {"path": "src/app_logic.py", "content": "def multiply(x, y):\n    return x + y  # BUG: addition instead of multiplication\n"},
            {"path": "test_logic.py", "content": "from src.app_logic import multiply\nassert multiply(3, 4) == 12, 'multiply(3, 4) should equal 12'\nprint('PASS')\n"}
        ]

        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands=ExecutionCommands(
                install="python --version",
                build="python -m py_compile src/app_logic.py",
                test="python test_logic.py"
            )
        )

        dod = DefinitionOfDone(items=[
            DoDItem(id="AC-TEST", description="Unit tests pass", verification_type="test")
        ])

        runner = E2BSandboxRunner()

        # Step 1: E2B Attempt 1 -> Expected TEST FAIL
        res1: ExecutionResult = asyncio.run(runner.execute("e2b_repair_cycle_101", initial_files, plan))
        self.assertEqual(res1.environment_used.get("runner"), "e2b_firecracker")
        self.assertEqual(res1.overall_status, "FAILED")
        self.assertEqual(res1.failed_stage, "TEST")

        qa1: QAReport = evaluate_qa_results(dod, res1)
        self.assertEqual(qa1.status, "FAIL")

        # Step 2: Build RepairContext & Patch
        repair_ctx = build_repair_context("e2b_repair_cycle_101", qa1, res1, dod, engineer_output={"files": initial_files})
        
        patch_res = PatchResult(
            status="PATCH_READY",
            changes=[
                FilePatch(
                    path="src/app_logic.py",
                    action="modify",
                    content="def multiply(x, y):\n    return x * y  # FIXED multiplication\n",
                    reason="Fix multiply logic bug"
                )
            ]
        )

        validated_patch = validate_patch(patch_res, repair_ctx)
        self.assertEqual(validated_patch.status, "PATCH_READY")

        # Step 3: Apply Patch
        applier = PatchApplier()
        apply_res, patched_files = applier.apply_patch("e2b_repair_cycle_101", validated_patch, initial_files, attempt=1)
        self.assertEqual(apply_res.status, "APPLIED")

        # Step 4: E2B Attempt 2 -> Expected TEST PASS
        res2: ExecutionResult = asyncio.run(runner.execute("e2b_repair_cycle_101", patched_files, plan))
        self.assertEqual(res2.environment_used.get("runner"), "e2b_firecracker")
        self.assertEqual(res2.overall_status, "PASSED")

        qa2: QAReport = evaluate_qa_results(dod, res2)
        self.assertEqual(qa2.status, "PASS")

        print("[PASS] Test 3: Real E2B Cloud Sandbox Re-Execution Repair Cycle PASSED.")


if __name__ == "__main__":
    unittest.main()
