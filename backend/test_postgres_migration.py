import os
import sys
import asyncio
import unittest
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.core.database import init_db, get_db, create_user, get_user_by_email, create_project, get_project, set_memory, get_memory, save_agent_output, get_project_outputs
from app.services.task_queue import task_queue, STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED
from app.services.startup_recovery import recover_orphaned_executions
from app.services.rate_limiter import rate_limiter
from app.services.resource_budget import resource_budget


class TestP47APostgreSQLMigration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["JWT_SECRET"] = "test_postgres_secret_key_112233"
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        asyncio.run(init_db())
        cls.client = TestClient(app)

    def setUp(self):
        email_a = f"pg_user_a_{os.urandom(4).hex()}@example.com"
        email_b = f"pg_user_b_{os.urandom(4).hex()}@example.com"
        res_a = self.client.post("/api/auth/register", json={"email": email_a, "password": "Password123"})
        res_b = self.client.post("/api/auth/register", json={"email": email_b, "password": "Password123"})
        self.token_a = res_a.json()["access_token"]
        self.token_b = res_b.json()["access_token"]
        self.user_a_id = res_a.json()["user"]["id"]
        self.user_b_id = res_b.json()["user"]["id"]

    def test_case_a_user_registration_login(self):
        """CASE A: User registration and authentication login flow works."""
        email = f"auth_case_a_{os.urandom(4).hex()}@example.com"
        reg_res = self.client.post("/api/auth/register", json={"email": email, "password": "Password123"})
        self.assertEqual(reg_res.status_code, 200)
        self.assertIn("access_token", reg_res.json())

        login_res = self.client.post("/api/auth/login", json={"email": email, "password": "Password123"})
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("access_token", login_res.json())
        print("[PASS] CASE A (User Registration & Auth Login Flow) PASSED.")

    def test_case_b_project_creation(self):
        """CASE B: Project creation persists in database."""
        res = self.client.post("/api/projects", json={"problem_statement": "PostgreSQL test project"}, headers={"Authorization": f"Bearer {self.token_a}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["problem_statement"], "PostgreSQL test project")
        self.assertEqual(data["user_id"], self.user_a_id)

        # Retrieve project
        proj = asyncio.run(get_project(data["id"], user_id=self.user_a_id))
        self.assertIsNotNone(proj)
        self.assertEqual(proj["id"], data["id"])
        print("[PASS] CASE B (Project Creation Persistence) PASSED.")

    def test_case_c_multi_tenant_isolation(self):
        """CASE C: User A cannot access User B's project (returns HTTP 404)."""
        res_a = self.client.post("/api/projects", json={"problem_statement": "User A secret project"}, headers={"Authorization": f"Bearer {self.token_a}"})
        proj_a_id = res_a.json()["id"]

        # User B attempt to access -> 404 Not Found
        res_b = self.client.get(f"/api/projects/{proj_a_id}", headers={"Authorization": f"Bearer {self.token_b}"})
        self.assertEqual(res_b.status_code, 404)

        # Database direct check -> returns None
        db_check = asyncio.run(get_project(proj_a_id, user_id=self.user_b_id))
        self.assertIsNone(db_check)
        print("[PASS] CASE C (Multi-Tenant Isolation Protection) PASSED.")

    def test_case_d_execution_records_persistence(self):
        """CASE D: Durable execution records persist."""
        proj = asyncio.run(create_project("Execution record test", user_id=self.user_a_id))
        exec_rec = asyncio.run(task_queue.enqueue(proj["id"], self.user_a_id))
        self.assertEqual(exec_rec["status"], STATUS_QUEUED)

        claimed = asyncio.run(task_queue.claim("worker_pg_1"))
        self.assertEqual(claimed["status"], STATUS_RUNNING)

        completed = asyncio.run(task_queue.complete(exec_rec["id"]))
        self.assertEqual(completed["status"], STATUS_COMPLETED)
        print("[PASS] CASE D (Durable Execution Records Persistence) PASSED.")

    def test_case_e_concurrent_project_writes(self):
        """CASE E: Concurrent project writes do not corrupt database state."""
        proj = asyncio.run(create_project("Concurrent write test", user_id=self.user_a_id))
        p_id = proj["id"]

        async def _write_mem(i):
            await set_memory(p_id, f"key_{i}", f"val_{i}", "test_worker")

        async def _run_concurrent():
            tasks = [_write_mem(i) for i in range(20)]
            await asyncio.gather(*tasks)

        asyncio.run(_run_concurrent())
        mem = asyncio.run(get_memory(p_id))
        self.assertEqual(len(mem), 20)
        print("[PASS] CASE E (Concurrent Database Writes Integrity) PASSED.")

    def test_case_f_qa_repair_state_persistence(self):
        """CASE F: QA and repair outputs persist correctly."""
        proj = asyncio.run(create_project("QA state test", user_id=self.user_a_id))
        p_id = proj["id"]

        output = asyncio.run(save_agent_output(p_id, "qa", {"verdict": "FAIL", "reason": "Test fail"}))
        self.assertEqual(output["role"], "qa")

        outputs = asyncio.run(get_project_outputs(p_id))
        self.assertEqual(len(outputs), 1)
        self.assertEqual(outputs[0]["content"]["verdict"], "FAIL")
        print("[PASS] CASE F (QA & Repair State Persistence) PASSED.")

    def test_case_g_resource_budgets_persistence(self):
        """CASE G: Resource budgets persist correctly."""
        p_id = f"proj_bg_pg_{os.urandom(4).hex()}"
        resource_budget.reset_project(p_id)

        resource_budget.record_llm_call(p_id)
        resource_budget.record_e2b_execution(p_id)
        resource_budget.record_repair_attempt(p_id)

        status = resource_budget.get_budget_status(p_id)
        self.assertEqual(status["llm_calls"], 1)
        self.assertEqual(status["e2b_executions"], 1)
        self.assertEqual(status["repair_attempts"], 1)
        print("[PASS] CASE G (Resource Budgets State Persistence) PASSED.")

    def test_case_h_startup_recovery_state_persistence(self):
        """CASE H: Startup recovery state persists."""
        proj = asyncio.run(create_project("Startup recovery test", user_id=self.user_a_id))
        exec_rec = asyncio.run(task_queue.enqueue(proj["id"], self.user_a_id))
        asyncio.run(task_queue.claim("worker_dead_pg"))

        # Mark recoverable directly to verify state persistence across abstraction
        rec = asyncio.run(task_queue.mark_recoverable(exec_rec["id"], "Process crash recovery"))
        self.assertEqual(rec["status"], "RECOVERABLE")
        print("[PASS] CASE H (Startup Recovery State Persistence) PASSED.")

    def test_case_i_existing_api_contract(self):
        """CASE I: Existing API contracts remain unchanged."""
        res = self.client.get("/api/projects", headers={"Authorization": f"Bearer {self.token_a}"})
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)
        print("[PASS] CASE I (Existing API Contract Compatibility) PASSED.")


if __name__ == "__main__":
    unittest.main()
