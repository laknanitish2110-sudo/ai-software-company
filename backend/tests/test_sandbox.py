import os
import sys
import json
import shutil
import tempfile
import asyncio
import unittest

# Add backend directory to sys.path
from app.services.file_generator import generate_project_files, PROJECTS_DIR
from app.models.execution_schema import validate_and_detect_execution_plan, ExecutionPlan
from app.services.sandbox_runner import (
    LocalSubprocessSandboxRunner,
    ExecutionResult,
    run_sandbox_execution
)


class TestP0SandboxImplementation(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"

    def setUp(self):
        self.test_pid = "test_pid_p0_123"

    def tearDown(self):
        # Cleanup generated project artifacts
        target_dir = PROJECTS_DIR / self.test_pid
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        zip_file = PROJECTS_DIR / f"{self.test_pid}.zip"
        if zip_file.exists():
            os.remove(zip_file)

    def test_p0_1_path_traversal_security(self):
        """P0.1: Verify path traversal attempt is safely blocked."""
        malicious_output = {
            "files": [
                {"path": "valid_file.js", "content": "console.log('hello');"},
                {"path": "../../../outside.txt", "content": "malicious write"},
                {"path": "/etc/passwd", "content": "root:x:0:0"},
            ]
        }
        zip_path = generate_project_files(self.test_pid, malicious_output)
        self.assertTrue(os.path.exists(zip_path))

        target_dir = PROJECTS_DIR / self.test_pid
        valid_path = target_dir / "valid_file.js"
        outside_path = (target_dir / "../../../outside.txt").resolve()

        self.assertTrue(valid_path.exists())
        self.assertFalse(outside_path.exists(), "Path traversal file should NOT have been created!")
        print("[PASS] P0.1 Path traversal security test PASSED.")

    def test_p0_2_p0_4_execution_plan_detection(self):
        """P0.2 & P0.4: Verify auto-detection of Node.js, Python, and n8n execution plans."""
        # Node / Next.js project
        node_out = {
            "files": [
                {"path": "package.json", "content": json.dumps({"scripts": {"build": "next build", "start": "next start"}})},
                {"path": "pages/index.js", "content": "export default () => <div>Hello</div>;"}
            ]
        }
        node_plan = validate_and_detect_execution_plan(node_out)
        self.assertEqual(node_plan.project_type, "node")
        self.assertEqual(node_plan.commands.install, "npm install")
        self.assertEqual(node_plan.commands.build, "npm run build")
        self.assertEqual(node_plan.commands.start, "npm start")

        # Python project
        py_out = {
            "files": [
                {"path": "requirements.txt", "content": "fastapi\nuvicorn\n"},
                {"path": "main.py", "content": "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef index(): return {'status':'ok'}"}
            ]
        }
        py_plan = validate_and_detect_execution_plan(py_out)
        self.assertEqual(py_plan.project_type, "python")
        self.assertEqual(py_plan.commands.install, "pip install -r requirements.txt")
        self.assertIn("main.py", py_plan.commands.build)

        # n8n workflow only
        n8n_out = {
            "n8n_workflow": {"name": "Test Workflow", "nodes": []},
            "deliverable_type": "workflow"
        }
        n8n_plan = validate_and_detect_execution_plan(n8n_out)
        self.assertEqual(n8n_plan.project_type, "n8n")
        self.assertFalse(n8n_plan.executable)

        print("[PASS] P0.2 & P0.4 Execution plan schema and auto-detection PASSED.")

    async def test_p0_3_p0_5_sandbox_runner_execution(self):
        """P0.3 & P0.5: Run 5-stage Sandbox execution (INSTALL -> BUILD -> TEST -> START -> HEALTH) and verify ExecutionResult."""
        py_project = {
            "files": [
                {"path": "requirements.txt", "content": "# no dependencies\n"},
                {"path": "main.py", "content": "print('Building...');"},
            ]
        }
        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands={
                "install": "python --version",
                "build": "python -m py_compile main.py",
                "test": "python -c \"assert 1 + 1 == 2\"",
                "start": "python -c \"import time; time.sleep(5)\"",
                "health_check": None
            }
        )

        runner = LocalSubprocessSandboxRunner()
        res: ExecutionResult = await runner.execute(self.test_pid, py_project["files"], plan)

        self.assertEqual(res.overall_status, "PASSED")
        self.assertEqual(res.stages["INSTALL"].status, "PASSED")
        self.assertEqual(res.stages["BUILD"].status, "PASSED")
        self.assertEqual(res.stages["TEST"].status, "PASSED")
        self.assertEqual(res.stages["START"].status, "PASSED")
        self.assertIsNone(res.failed_stage)

        print(f"[PASS] P0.3 & P0.5 5-stage Sandbox execution PASSED in {res.duration_ms}ms.")

    async def test_p0_6_failing_stage_detection(self):
        """P0.6: Verify failing stage halts execution cleanly and produces structured error signature."""
        broken_project = {
            "files": [
                {"path": "main.py", "content": "invalid python syntax ==="}
            ]
        }
        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands={
                "install": "python --version",
                "build": "python -m py_compile main.py",
                "test": "pytest",
                "start": "python main.py"
            }
        )

        res: ExecutionResult = await run_sandbox_execution(self.test_pid, broken_project["files"], plan)

        self.assertEqual(res.overall_status, "FAILED")
        self.assertEqual(res.failed_stage, "BUILD")
        self.assertEqual(res.stages["INSTALL"].status, "PASSED")
        self.assertEqual(res.stages["BUILD"].status, "FAILED")
        self.assertEqual(res.stages["TEST"].status, "SKIPPED")
        self.assertIsNotNone(res.error_signature)

        print(f"[PASS] P0.6 Failing stage detection and ExecutionResult formatting PASSED.")


if __name__ == "__main__":
    unittest.main()
