import os
import sys
import asyncio
import unittest
from unittest.mock import patch, MagicMock

from app.models.execution_schema import ExecutionPlan, ExecutionCommands
from app.services.sandbox_runner import (
    get_sandbox_runner,
    run_sandbox_execution,
    E2BSandboxRunner,
    LocalSubprocessSandboxRunner,
    SandboxUnavailableError,
    ExecutionResult
)
from app.core.config import validate_sandbox_config


class TestP42SandboxSecurity(unittest.TestCase):

    def test_case_a_production_valid_e2b(self):
        """CASE A: Production environment + valid E2B key -> E2BSandboxRunner selected."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "SANDBOX_MODE": "e2b_required", "E2B_API_KEY": "e2b_valid_mock_key"}):
            runner = get_sandbox_runner(env="production", mode="e2b_required")
            self.assertIsInstance(runner, E2BSandboxRunner)
        print("[PASS] CASE A (Production + Valid E2B -> E2BSandboxRunner Selected) PASSED.")

    def test_case_b_production_missing_e2b_key(self):
        """CASE B: Production environment + missing E2B key -> Execution rejected (SANDBOX_INIT failure). Local runner NOT called."""
        plan = ExecutionPlan(project_type="python", executable=True, commands=ExecutionCommands(test="python test.py"))
        files = [{"path": "test.py", "content": "print('hello')"}]

        with patch.dict(os.environ, {"ENVIRONMENT": "production", "SANDBOX_MODE": "e2b_required", "E2B_API_KEY": ""}):
            with patch.object(LocalSubprocessSandboxRunner, "execute") as mock_local:
                res = asyncio.run(run_sandbox_execution("test_proj_b", files, plan))
                self.assertEqual(res.overall_status, "FAILED")
                self.assertEqual(res.failed_stage, "SANDBOX_INIT")
                self.assertIn("E2B API key missing", res.stages["SANDBOX_INIT"].stderr_snippet)
                mock_local.assert_not_called()
        print("[PASS] CASE B (Production + Missing E2B Key -> Host Execution Blocked & SANDBOX_INIT Failure) PASSED.")

    def test_case_c_production_e2b_creation_failure(self):
        """CASE C: Production environment + E2B creation failure -> Execution rejected cleanly. Local runner NOT called."""
        plan = ExecutionPlan(project_type="python", executable=True, commands=ExecutionCommands(test="python test.py"))
        files = [{"path": "test.py", "content": "print('hello')"}]

        with patch.dict(os.environ, {"ENVIRONMENT": "production", "SANDBOX_MODE": "e2b_required", "E2B_API_KEY": "e2b_mock_key"}):
            with patch("app.services.sandbox_runner.E2BSandboxRunner.execute", side_effect=SandboxUnavailableError("E2B creation timeout")):
                with patch.object(LocalSubprocessSandboxRunner, "execute") as mock_local:
                    res = asyncio.run(run_sandbox_execution("test_proj_c", files, plan))
                    self.assertEqual(res.overall_status, "FAILED")
                    self.assertEqual(res.failed_stage, "SANDBOX_INIT")
                    mock_local.assert_not_called()
        print("[PASS] CASE C (Production + E2B Creation Failure -> Host Execution Blocked) PASSED.")

    def test_case_d_development_local_dev_allowed(self):
        """CASE D: Development environment + SANDBOX_MODE=local_dev -> Local runner allowed."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "SANDBOX_MODE": "local_dev"}):
            runner = get_sandbox_runner(env="development", mode="local_dev")
            self.assertIsInstance(runner, LocalSubprocessSandboxRunner)
        print("[PASS] CASE D (Development + local_dev Mode -> Local Runner Allowed) PASSED.")

    def test_case_e_production_local_dev_rejected(self):
        """CASE E: Production environment + SANDBOX_MODE=local_dev -> Configuration rejected."""
        with self.assertRaises(ValueError) as ctx:
            validate_sandbox_config(env="production", mode="local_dev")
        self.assertIn("strictly forbidden in production", str(ctx.exception))
        print("[PASS] CASE E (Production + local_dev Mode -> Config Validation Rejection) PASSED.")

    def test_case_f_invalid_sandbox_mode(self):
        """CASE F: Invalid SANDBOX_MODE -> Configuration rejected."""
        with self.assertRaises(ValueError) as ctx:
            validate_sandbox_config(env="development", mode="invalid_mode")
        self.assertIn("Invalid SANDBOX_MODE", str(ctx.exception))
        print("[PASS] CASE F (Invalid SANDBOX_MODE -> Config Validation Rejection) PASSED.")

    def test_case_g_host_isolation_verification(self):
        """CASE G: Verify zero generated code is executed on the host OS when E2B fails."""
        plan = ExecutionPlan(project_type="python", executable=True, commands=ExecutionCommands(test="python -c \"import sys; sys.exit(99)\""))
        files = [{"path": "malicious.py", "content": "import os; os.system('echo HACKED > hacked.txt')"}]

        with patch.dict(os.environ, {"ENVIRONMENT": "production", "SANDBOX_MODE": "e2b_required", "E2B_API_KEY": ""}):
            res = asyncio.run(run_sandbox_execution("test_proj_g", files, plan))
            self.assertEqual(res.overall_status, "FAILED")
            self.assertEqual(res.failed_stage, "SANDBOX_INIT")
            self.assertFalse(os.path.exists("hacked.txt"))
        print("[PASS] CASE G (Host Execution Isolation Verified — 0 Host Commands Executed) PASSED.")


if __name__ == "__main__":
    unittest.main()
