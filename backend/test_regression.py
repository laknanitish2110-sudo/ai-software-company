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
    FilePatch,
    ExecutionBaseline,
    RegressionResult
)
from app.services.sandbox_runner import (
    LocalSubprocessSandboxRunner,
    E2BSandboxRunner,
    ExecutionResult,
    StageResult
)
from app.services.regression_checker import (
    capture_baseline,
    compare_execution_baseline,
    RegressionChecker
)
from app.agents.qa import evaluate_qa_results
from app.services.repair_context_builder import build_repair_context
from app.agents.fixer import validate_patch
from app.services.patch_applier import PatchApplier, PROJECTS_DIR


class TestP24RegressionChecker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"

    def setUp(self):
        self.test_pid = "test_p24_reg_pid_55"
        self.project_dir = PROJECTS_DIR / self.test_pid
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir, ignore_errors=True)
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir, ignore_errors=True)

    def test_case_a_safe_repair(self):
        """CASE A: Before: BUILD ✓, TEST-A ✓, TEST-B ✗ -> After: BUILD ✓, TEST-A ✓, TEST-B ✓ -> SAFE_TO_ACCEPT."""
        res_before = ExecutionResult(
            project_id=self.test_pid,
            overall_status="FAILED",
            failed_stage="TEST",
            stages={
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="FAILED", exit_code=1, stdout_snippet="TEST-A PASSED\nTEST-B FAILED\n")
            }
        )

        res_after = ExecutionResult(
            project_id=self.test_pid,
            overall_status="PASSED",
            stages={
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="PASSED", exit_code=0, stdout_snippet="TEST-A PASSED\nTEST-B PASSED\n")
            }
        )

        baseline = capture_baseline(res_before)
        self.assertIn("TEST-A", baseline.passed_checks)
        self.assertIn("TEST-B", baseline.failed_checks)

        reg_result = compare_execution_baseline(baseline, res_after)
        self.assertEqual(reg_result.status, "SAFE_TO_ACCEPT")
        self.assertTrue(reg_result.safe_to_accept)
        self.assertIn("TEST-B", reg_result.fixed_failures)
        self.assertEqual(len(reg_result.regressions), 0)
        print("[PASS] CASE A (Safe Repair) PASSED.")

    def test_case_b_regression_detected(self):
        """CASE B: Before: BUILD ✓, TEST-A ✓, TEST-B ✗ -> After: BUILD ✓, TEST-A ✗, TEST-B ✓ -> REGRESSION."""
        res_before = ExecutionResult(
            project_id=self.test_pid,
            overall_status="FAILED",
            failed_stage="TEST",
            stages={
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="FAILED", exit_code=1, stdout_snippet="TEST-A PASSED\nTEST-B FAILED\n")
            }
        )

        res_after = ExecutionResult(
            project_id=self.test_pid,
            overall_status="FAILED",
            failed_stage="TEST",
            stages={
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="FAILED", exit_code=1, stdout_snippet="TEST-A FAILED\nTEST-B PASSED\n")
            }
        )

        baseline = capture_baseline(res_before)
        reg_result = compare_execution_baseline(baseline, res_after)

        self.assertEqual(reg_result.status, "REGRESSION")
        self.assertFalse(reg_result.safe_to_accept)
        self.assertIn("TEST-A", reg_result.regressions)
        print("[PASS] CASE B (Regression Detected) PASSED.")

    def test_case_c_failure_remains(self):
        """CASE C: Before: BUILD ✓, TEST-A ✓, TEST-B ✗ -> After: BUILD ✓, TEST-A ✓, TEST-B ✗ -> REPAIR_FAILED."""
        res_before = ExecutionResult(
            project_id=self.test_pid,
            overall_status="FAILED",
            failed_stage="TEST",
            stages={
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="FAILED", exit_code=1, stdout_snippet="TEST-A PASSED\nTEST-B FAILED\n")
            }
        )

        res_after = ExecutionResult(
            project_id=self.test_pid,
            overall_status="FAILED",
            failed_stage="TEST",
            stages={
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="FAILED", exit_code=1, stdout_snippet="TEST-A PASSED\nTEST-B FAILED\n")
            }
        )

        baseline = capture_baseline(res_before)
        reg_result = compare_execution_baseline(baseline, res_after)

        self.assertEqual(reg_result.status, "REPAIR_FAILED")
        self.assertFalse(reg_result.safe_to_accept)
        self.assertIn("TEST-B", reg_result.unchanged_failures)
        print("[PASS] CASE C (Failure Remains REPAIR_FAILED) PASSED.")

    def test_case_d_new_stage_failure_regression(self):
        """CASE D: Before: BUILD ✓, TEST-A ✓, TEST-B ✗ -> After: BUILD ✗ (syntax error in patch) -> REGRESSION."""
        res_before = ExecutionResult(
            project_id=self.test_pid,
            overall_status="FAILED",
            failed_stage="TEST",
            stages={
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="FAILED", exit_code=1, stdout_snippet="TEST-A PASSED\nTEST-B FAILED\n")
            }
        )

        res_after = ExecutionResult(
            project_id=self.test_pid,
            overall_status="FAILED",
            failed_stage="BUILD",
            stages={
                "BUILD": StageResult(status="FAILED", exit_code=1, stderr_snippet="SyntaxError: invalid syntax"),
                "TEST": StageResult(status="SKIPPED")
            }
        )

        baseline = capture_baseline(res_before)
        reg_result = compare_execution_baseline(baseline, res_after)

        self.assertEqual(reg_result.status, "REGRESSION")
        self.assertFalse(reg_result.safe_to_accept)
        self.assertIn("BUILD", reg_result.reason)
        print("[PASS] CASE D (New Stage Failure REGRESSION) PASSED.")

    def test_case_e_real_e2b_cloud_regression_validation(self):
        """CASE E: Real AWS Firecracker E2B Cloud Sandbox Regression Validation & Automatic Rollback."""
        api_key = os.getenv("E2B_API_KEY", "")
        if not api_key:
            print("[SKIP] CASE E: E2B_API_KEY unavailable for live E2B regression test.")
            return

        initial_files = [
            {"path": "requirements.txt", "content": ""},
            {"path": "src/calc.py", "content": "def mult(a, b): return a * b  # Working\ndef add(a, b): return a - b   # BROKEN\n"},
            {"path": "test_calc.py", "content": (
                "from src.calc import mult, add\n"
                "if mult(2, 2) == 4: print('TEST-A PASSED')\n"
                "else: print('TEST-A FAILED')\n"
                "if add(2, 3) == 5: print('TEST-B PASSED')\n"
                "else:\n"
                "    print('TEST-B FAILED')\n"
                "    assert False, 'TEST-B FAILED'\n"
            )}
        ]

        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands=ExecutionCommands(
                install="python --version",
                build="python -m py_compile src/calc.py",
                test="python test_calc.py"
            )
        )

        runner = E2BSandboxRunner()

        # Step 1: E2B Attempt 1 -> TEST-A passes, TEST-B fails
        res1: ExecutionResult = asyncio.run(runner.execute("e2b_reg_test_202", initial_files, plan))
        self.assertEqual(res1.environment_used.get("runner"), "e2b_firecracker")
        self.assertEqual(res1.overall_status, "FAILED")

        baseline = capture_baseline(res1)
        self.assertIn("TEST-A", baseline.passed_checks)
        self.assertIn("TEST-B", baseline.failed_checks)

        # Step 2: Apply Regressive Patch (Fixes add, but breaks mult!)
        regressive_patch = PatchResult(
            status="PATCH_READY",
            changes=[
                FilePatch(
                    path="src/calc.py",
                    action="modify",
                    content="def mult(a, b): return 99  # INTENTIONALLY BROKEN\ndef add(a, b): return a + b   # FIXED\n",
                    reason="Fix add but introduce regression in mult"
                )
            ]
        )

        applier = PatchApplier()
        snapshot = applier.create_snapshot("e2b_reg_test_202", initial_files)
        apply_res, patched_files = applier.apply_patch("e2b_reg_test_202", regressive_patch, initial_files, attempt=1)
        self.assertEqual(apply_res.status, "APPLIED")

        # Step 3: E2B Attempt 2 -> TEST-A fails (REGRESSION), TEST-B passes
        res2: ExecutionResult = asyncio.run(runner.execute("e2b_reg_test_202", patched_files, plan))

        reg_result = compare_execution_baseline(baseline, res2)
        self.assertEqual(reg_result.status, "REGRESSION")
        self.assertFalse(reg_result.safe_to_accept)
        self.assertIn("TEST-A", reg_result.regressions)

        # Step 4: Perform Rollback and Verify Files Restored
        restored_files = applier.rollback_snapshot("e2b_reg_test_202", snapshot, patched_files)
        calc_content = [f["content"] for f in restored_files if f["path"] == "src/calc.py"][0]
        self.assertIn("def mult(a, b): return a * b", calc_content)
        self.assertNotIn("return 99", calc_content)

        print("[PASS] CASE E: Real E2B Cloud Sandbox Regression & Rollback PASSED.")


if __name__ == "__main__":
    unittest.main()
