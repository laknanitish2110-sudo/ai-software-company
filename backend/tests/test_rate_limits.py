import os
import sys
import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db
from app.services.rate_limiter import rate_limiter
from app.services.resource_budget import resource_budget, ResourceBudgetExceededError
from app.services.sandbox_runner import run_sandbox_execution, LocalSubprocessSandboxRunner
from app.models.execution_schema import ExecutionPlan, ExecutionCommands
from app.services.orchestrator import orchestrator


class TestP44RateLimitsAndResourceProtection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET"] = "test_rate_limit_secret_key_12345"
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        asyncio.run(init_db())
        cls.client = TestClient(app)

    def setUp(self):
        # Register User A & User B
        email_a = f"rate_a_{os.urandom(4).hex()}@example.com"
        email_b = f"rate_b_{os.urandom(4).hex()}@example.com"
        res_a = self.client.post("/api/auth/register", json={"email": email_a, "password": "Password123"})
        res_b = self.client.post("/api/auth/register", json={"email": email_b, "password": "Password123"})
        self.token_a = res_a.json()["access_token"]
        self.token_b = res_b.json()["access_token"]
        self.user_a_id = res_a.json()["user"]["id"]
        self.user_b_id = res_b.json()["user"]["id"]
        
        rate_limiter.reset_user(self.user_a_id)
        rate_limiter.reset_user(self.user_b_id)

    def test_case_a_user_below_rate_limit(self):
        """CASE A: User below rate limit -> request allowed (HTTP 200)."""
        allowed, retry_after = asyncio.run(rate_limiter.check_rate_limit(user_id=self.user_a_id, action="create", limit=5))
        self.assertTrue(allowed)
        self.assertEqual(retry_after, 0)
        print("[PASS] CASE A (User Below Rate Limit Allowed) PASSED.")

    def test_case_b_user_exceeds_request_rate(self):
        """CASE B: User exceeds request rate -> HTTP 429 Too Many Requests."""
        user_id = f"test_user_rate_b_{os.urandom(4).hex()}"
        # Exhaust 3 allowed project creation requests
        for _ in range(3):
            asyncio.run(rate_limiter.check_rate_limit(user_id=user_id, action="create", limit=3))

        # 4th request -> Rate Limited
        allowed, retry_after = asyncio.run(rate_limiter.check_rate_limit(user_id=user_id, action="create", limit=3))
        self.assertFalse(allowed)
        self.assertGreater(retry_after, 0)

        # HTTP Endpoint check
        with patch.object(rate_limiter, "check_rate_limit", new=AsyncMock(return_value=(False, 30))):
            res = self.client.post("/api/projects", json={"problem_statement": "Rate test"}, headers={"Authorization": f"Bearer {self.token_a}"})
            self.assertEqual(res.status_code, 429)
            self.assertEqual(res.json()["error"], "RATE_LIMITED")
            self.assertEqual(res.json()["retry_after_seconds"], 30)
        print("[PASS] CASE B (User Exceeds Request Rate -> HTTP 429 Returned) PASSED.")

    def test_case_c_project_exceeds_execution_budget(self):
        """CASE C: Project exceeds execution budget -> RESOURCE_BUDGET_EXCEEDED."""
        proj_id = f"proj_budget_c_{os.urandom(4).hex()}"
        resource_budget.reset_project(proj_id)

        # Exhaust LLM calls limit (set to 3 for testing)
        for _ in range(3):
            resource_budget.record_llm_call(proj_id)

        with self.assertRaises(ResourceBudgetExceededError) as ctx:
            resource_budget.check_llm_budget(proj_id, max_limit=3)
        self.assertIn("RESOURCE_BUDGET_EXCEEDED", str(ctx.exception))
        
        status = resource_budget.get_budget_status(proj_id)
        self.assertEqual(status["llm_calls"], 3)
        print("[PASS] CASE C (Project Exceeds Resource Budget -> RESOURCE_BUDGET_EXCEEDED) PASSED.")

    def test_case_d_budget_exhausted_before_e2b(self):
        """CASE D: E2B Budget exhausted -> E2B runner is NOT invoked & SANDBOX_INIT failure returned."""
        proj_id = f"proj_budget_d_{os.urandom(4).hex()}"
        resource_budget.reset_project(proj_id)

        # Record max E2B executions (e.g. 2)
        resource_budget.record_e2b_execution(proj_id)
        resource_budget.record_e2b_execution(proj_id)

        plan = ExecutionPlan(project_type="python", executable=True, commands=ExecutionCommands(test="python test.py"))
        files = [{"path": "test.py", "content": "print('hello')"}]

        with patch.object(LocalSubprocessSandboxRunner, "execute") as mock_runner:
            with patch("app.services.resource_budget.MAX_E2B_EXECUTIONS_PER_PROJECT", 2):
                res = asyncio.run(run_sandbox_execution(proj_id, files, plan))
                self.assertEqual(res.overall_status, "FAILED")
                self.assertEqual(res.failed_stage, "SANDBOX_INIT")
                self.assertIn("RESOURCE_BUDGET_EXCEEDED", res.stages["SANDBOX_INIT"].stderr_snippet)
                mock_runner.assert_not_called()
        print("[PASS] CASE D (Budget Exhausted Before E2B -> E2B Runner NOT Invoked) PASSED.")

    def test_case_e_budget_exhausted_before_llm(self):
        """CASE E: LLM Budget exhausted -> LLM call is NOT invoked."""
        proj_id = f"proj_budget_e_{os.urandom(4).hex()}"
        resource_budget.reset_project(proj_id)

        # Exhaust LLM budget
        resource_budget.record_llm_call(proj_id)
        resource_budget.record_llm_call(proj_id)

        from app.agents.engine import _llm_call_with_retry

        with patch("app.agents.engine.get_client") as mock_get_client:
            with patch("app.services.resource_budget.MAX_LLM_CALLS_PER_PROJECT", 2):
                with self.assertRaises(ResourceBudgetExceededError):
                    asyncio.run(_llm_call_with_retry("gpt-4o", [{"role": "user", "content": "hi"}], 100, 5, project_id=proj_id))
                mock_get_client.assert_not_called()
        print("[PASS] CASE E (Budget Exhausted Before LLM -> LLM Call NOT Invoked) PASSED.")

    def test_case_f_repair_attempts_limited_to_3(self):
        """CASE F: Repair attempts remain limited to 3 -> Attempt 4 never occurs."""
        proj_id = f"proj_budget_f_{os.urandom(4).hex()}"
        resource_budget.reset_project(proj_id)

        resource_budget.record_repair_attempt(proj_id)
        resource_budget.record_repair_attempt(proj_id)
        resource_budget.record_repair_attempt(proj_id)

        with self.assertRaises(ResourceBudgetExceededError) as ctx:
            resource_budget.check_repair_budget(proj_id)
        self.assertIn("max repair attempts ceiling", str(ctx.exception))
        print("[PASS] CASE F (Repair Attempts Authoritatively Limited to 3 Ceiling) PASSED.")

    def test_case_g_duplicate_request_prevention(self):
        """CASE G: Two duplicate run requests for the same project -> Second request rejected."""
        proj_id = f"dup_proj_{os.urandom(4).hex()}"
        
        # 1. Register first execution
        token = asyncio.run(orchestrator.register_project_execution(proj_id))
        try:
            # 2. Duplicate registration attempt -> REJECTED with ValueError
            with self.assertRaises(ValueError) as ctx:
                asyncio.run(orchestrator.register_project_execution(proj_id))
            self.assertIn("PROJECT_EXECUTION_IN_PROGRESS", str(ctx.exception))
        finally:
            orchestrator._active_executions.discard(proj_id)
        print("[PASS] CASE G (Duplicate Execution Request -> Conflict Blocked) PASSED.")

    def test_case_h_independent_user_rate_limits(self):
        """CASE H: User A reaching rate limit does not affect User B."""
        user_a = f"user_indep_a_{os.urandom(4).hex()}"
        user_b = f"user_indep_b_{os.urandom(4).hex()}"

        # Exhaust User A's rate limit
        for _ in range(2):
            asyncio.run(rate_limiter.check_rate_limit(user_id=user_a, action="create", limit=2))

        allowed_a, _ = asyncio.run(rate_limiter.check_rate_limit(user_id=user_a, action="create", limit=2))
        self.assertFalse(allowed_a)

        # User B should still be allowed
        allowed_b, _ = asyncio.run(rate_limiter.check_rate_limit(user_id=user_b, action="create", limit=2))
        self.assertTrue(allowed_b)
        print("[PASS] CASE H (Independent Multi-Tenant Rate Limits Verified) PASSED.")


if __name__ == "__main__":
    unittest.main()
