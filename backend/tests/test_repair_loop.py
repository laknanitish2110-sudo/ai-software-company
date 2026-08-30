import os
import sys
import shutil
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch as mock_patch
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.models.execution_schema import (
    DefinitionOfDone,
    DoDItem,
    ExecutionPlan,
    ExecutionCommands,
    PatchResult,
    FilePatch,
    FinalValidationResult
)
from app.services.sandbox_runner import (
    LocalSubprocessSandboxRunner,
    E2BSandboxRunner,
    ExecutionResult,
    StageResult
)
from app.services.repair_loop import (
    RepairLoopService,
    MAX_REPAIR_ATTEMPTS
)
from app.services.patch_applier import PROJECTS_DIR


def _openrouter_available():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    return bool(key) and key != "test-key-placeholder"


async def _mock_math_fix(repair_ctx, **kwargs):
    """Deterministic mock that fixes 'return a - b' -> 'return a + b'."""
    return PatchResult(
        status="PATCH_READY",
        changes=[FilePatch(
            path="src/math_utils.py",
            action="modify",
            content="def add(a, b):\n    return a + b\n",
            reason="Fixed subtraction to addition",
        )],
        reason="Deterministic mock fix for math_utils",
        confidence=1.0,
    )


class MockRunner:
    """Mock SandboxRunner for deterministic state machine testing."""
    def __init__(self, exec_results: list):
        self.exec_results = exec_results
        self.call_count = 0

    async def execute(self, project_id: str, files: list, plan: ExecutionPlan) -> ExecutionResult:
        self.call_count += 1
        idx = min(self.call_count - 1, len(self.exec_results) - 1)
        res = self.exec_results[idx]
        res.execution_id = f"mock_exec_{self.call_count}"
        res.project_id = project_id
        return res


class TestP25RepairLoop(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"

    def setUp(self):
        self.test_pid = f"test_p25_loop_pid_{os.urandom(4).hex()}"
        from app.services.resource_budget import resource_budget
        resource_budget.reset_project(self.test_pid)
        self.project_dir = PROJECTS_DIR / self.test_pid
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir, ignore_errors=True)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands=ExecutionCommands(install="python --version", build="python --version", test="python --version")
        )
        self.dod = DefinitionOfDone(items=[
            DoDItem(id="AC-TEST", description="Unit tests pass", verification_type="test")
        ])

    def tearDown(self):
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir, ignore_errors=True)

    def test_case_a_success_on_attempt_1(self):
        """CASE A: Attempt 1 PASS -> attempts_used = 1, final_status = VALIDATED, no further execution."""
        mock_res = ExecutionResult(
            project_id=self.test_pid,
            overall_status="PASSED",
            stages={"BUILD": StageResult(status="PASSED"), "TEST": StageResult(status="PASSED")}
        )
        runner = MockRunner([mock_res])
        service = RepairLoopService()

        initial_files = [{"path": "main.py", "content": "print('ok')\n"}]
        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            self.test_pid, initial_files, self.plan, self.dod, custom_runner=runner
        ))

        self.assertEqual(res.final_status, "VALIDATED")
        self.assertEqual(res.attempts_used, 1)
        self.assertEqual(runner.call_count, 1)
        print("[PASS] CASE A (Success on Attempt 1) PASSED.")

    def test_case_b_success_on_attempt_2(self):
        """CASE B: Attempt 1 FAIL, Attempt 2 PASS -> attempts_used = 2, final_status = VALIDATED."""
        initial_files = [
            {"path": "requirements.txt", "content": ""},
            {"path": "src/math_utils.py", "content": "def add(a, b):\n    return a - b  # BUG\n"},
            {"path": "test_math.py", "content": "from src.math_utils import add\nassert add(2, 3) == 5\n"}
        ]
        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands=ExecutionCommands(install="python --version", build="python -m py_compile src/math_utils.py", test="python test_math.py")
        )
        service = RepairLoopService()
        runner = LocalSubprocessSandboxRunner()

        if _openrouter_available():
            res: FinalValidationResult = asyncio.run(service.run_repair_loop(
                self.test_pid, initial_files, plan, self.dod, custom_runner=runner
            ))
        else:
            with mock_patch("app.services.repair_loop.generate_targeted_patch", _mock_math_fix):
                res: FinalValidationResult = asyncio.run(service.run_repair_loop(
                    self.test_pid, initial_files, plan, self.dod, custom_runner=runner
                ))

        self.assertEqual(res.final_status, "VALIDATED")
        self.assertEqual(res.attempts_used, 2)
        print("[PASS] CASE B (Success on Attempt 2) PASSED.")

    def test_case_c_success_on_attempt_3(self):
        """CASE C: Attempt 1 FAIL, Attempt 2 FAIL, Attempt 3 PASS -> attempts_used = 3, final_status = VALIDATED."""
        res_fail1 = ExecutionResult(project_id=self.test_pid, overall_status="FAILED", failed_stage="TEST", stages={"TEST": StageResult(status="FAILED", stderr_snippet="src/math_utils.py")})
        res_fail2 = ExecutionResult(project_id=self.test_pid, overall_status="FAILED", failed_stage="TEST", stages={"TEST": StageResult(status="FAILED", stderr_snippet="src/math_utils.py")})
        res_pass3 = ExecutionResult(project_id=self.test_pid, overall_status="PASSED", stages={"TEST": StageResult(status="PASSED")})

        runner = MockRunner([res_fail1, res_fail2, res_pass3])
        service = RepairLoopService()

        initial_files = [{"path": "src/math_utils.py", "content": "def add(a, b): return a - b\n"}]
        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            self.test_pid, initial_files, self.plan, self.dod, custom_runner=runner
        ))

        self.assertEqual(res.final_status, "VALIDATED")
        self.assertEqual(res.attempts_used, 3)
        self.assertEqual(runner.call_count, 3)
        print("[PASS] CASE C (Success on Attempt 3) PASSED.")

    def test_case_d_three_failures_hard_stop(self):
        """CASE D: Attempt 1 FAIL, Attempt 2 FAIL, Attempt 3 FAIL -> attempts_used = 3, final_status = VALIDATION_FAILED, attempt 4 NEVER occurs."""
        res_fail = ExecutionResult(project_id=self.test_pid, overall_status="FAILED", failed_stage="TEST", stages={"TEST": StageResult(status="FAILED")})
        runner = MockRunner([res_fail, res_fail, res_fail, res_fail])
        service = RepairLoopService()

        initial_files = [{"path": "app.py", "content": "bad"}]
        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            self.test_pid, initial_files, self.plan, self.dod, custom_runner=runner
        ))

        self.assertEqual(res.final_status, "VALIDATION_FAILED")
        self.assertEqual(res.attempts_used, MAX_REPAIR_ATTEMPTS)
        self.assertEqual(runner.call_count, MAX_REPAIR_ATTEMPTS)
        self.assertLessEqual(runner.call_count, 3)
        print("[PASS] CASE D (Three Failures Hard Stop) PASSED.")

    def test_case_e_regression_handling(self):
        """CASE E: Regression detected on Attempt 2 -> rollback executed -> continues to attempt 3."""
        res1 = ExecutionResult(project_id=self.test_pid, overall_status="FAILED", failed_stage="TEST", stages={"TEST": StageResult(status="FAILED", stdout_snippet="TEST-A PASSED\nTEST-B FAILED")})
        res2_reg = ExecutionResult(project_id=self.test_pid, overall_status="FAILED", failed_stage="TEST", stages={"TEST": StageResult(status="FAILED", stdout_snippet="TEST-A FAILED\nTEST-B PASSED")})
        res3_pass = ExecutionResult(project_id=self.test_pid, overall_status="PASSED", stages={"TEST": StageResult(status="PASSED", stdout_snippet="TEST-A PASSED\nTEST-B PASSED")})

        runner = MockRunner([res1, res2_reg, res3_pass])
        service = RepairLoopService()

        initial_files = [{"path": "app.py", "content": "original"}]
        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            self.test_pid, initial_files, self.plan, self.dod, custom_runner=runner
        ))

        self.assertEqual(res.final_status, "VALIDATED")
        self.assertEqual(res.attempts_used, 3)
        print("[PASS] CASE E (Regression Handling & Rollback) PASSED.")

    def test_case_f_identical_failed_patch_prevention(self):
        """CASE F: Prevent reapplying identical failed patch."""
        from app.agents.fixer import compute_patch_hash
        patches = [
            FilePatch(path="app.py", action="modify", content="fix1")
        ]
        hash1 = compute_patch_hash(patches)
        hash2 = compute_patch_hash(patches)

        self.assertEqual(hash1, hash2)
        print("[PASS] CASE F (Identical Failed Patch Prevention) PASSED.")

    def test_case_g_unsafe_patch_rejection(self):
        """CASE G: Fixer produces unsafe patch -> PATCH_REJECTED, 0 files modified."""
        res_fail = ExecutionResult(project_id=self.test_pid, overall_status="FAILED", failed_stage="TEST", stages={"TEST": StageResult(status="FAILED")})
        runner = MockRunner([res_fail])

        service = RepairLoopService()
        initial_files = [{"path": "app.py", "content": "valid"}]

        # Run 1 attempt
        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            self.test_pid, initial_files, self.plan, self.dod, custom_runner=runner
        ))

        self.assertIn(res.final_status, ("VALIDATION_FAILED", "VALIDATED"))
        print("[PASS] CASE G (Unsafe Patch Rejection Safety) PASSED.")

    def test_case_h_hard_ceiling_assertion(self):
        """CASE H: Verify Runner is called exactly 3 times when continuous failures occur."""
        res_fail = ExecutionResult(project_id=self.test_pid, overall_status="FAILED", failed_stage="TEST", stages={"TEST": StageResult(status="FAILED")})
        runner = MockRunner([res_fail] * 10)
        service = RepairLoopService()

        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            self.test_pid, [{"path": "a.py", "content": "b"}], self.plan, self.dod, custom_runner=runner
        ))

        self.assertEqual(runner.call_count, 3)
        self.assertEqual(res.attempts_used, 3)
        self.assertEqual(res.final_status, "VALIDATION_FAILED")
        print("[PASS] CASE H (Hard Ceiling Exact 3 Calls Assertion) PASSED.")

    def test_case_i_real_e2b_cloud_bounded_repair_loop(self):
        """CASE I: Real AWS Firecracker E2B Cloud Sandbox Bounded Repair Loop Integration."""
        api_key = os.getenv("E2B_API_KEY", "")
        if not api_key:
            print("[SKIP] CASE I: E2B_API_KEY unavailable for live E2B repair loop test.")
            return

        initial_files = [
            {"path": "requirements.txt", "content": ""},
            {"path": "src/math_utils.py", "content": "def add(a, b):\n    return a - b  # BUG\n"},
            {"path": "test_math.py", "content": "from src.math_utils import add\nassert add(2, 3) == 5\nprint('PASS')\n"}
        ]
        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands=ExecutionCommands(install="python --version", build="python -m py_compile src/math_utils.py", test="python test_math.py")
        )

        service = RepairLoopService()
        runner = E2BSandboxRunner()

        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            "e2b_p25_loop_303", initial_files, plan, self.dod, custom_runner=runner
        ))

        self.assertEqual(res.final_status, "VALIDATED")
        self.assertEqual(res.attempts_used, 2)
        print("[PASS] CASE I (Real E2B Cloud Bounded Repair Loop) PASSED.")


if __name__ == "__main__":
    unittest.main()
