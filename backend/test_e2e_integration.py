import os
import sys
import time
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
    FinalValidationResult
)
from app.services.sandbox_runner import E2BSandboxRunner, LocalSubprocessSandboxRunner
from app.services.repair_loop import RepairLoopService
from app.services.patch_applier import PROJECTS_DIR


class TestP3E2EIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"

    def setUp(self):
        self.project_a_id = "e2e_task_mgr_run_a"
        self.project_b_id = "e2e_task_mgr_run_b"
        
        for pid in (self.project_a_id, self.project_b_id):
            pdir = PROJECTS_DIR / pid
            if pdir.exists():
                shutil.rmtree(pdir, ignore_errors=True)
            pdir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for pid in (self.project_a_id, self.project_b_id):
            pdir = PROJECTS_DIR / pid
            if pdir.exists():
                shutil.rmtree(pdir, ignore_errors=True)

    def test_run_a_clean_project_execution(self):
        """RUN A: End-to-end execution of a clean Task Management API project (Expected: PASS on Attempt 1)."""
        files_run_a = [
            {"path": "requirements.txt", "content": ""},
            {
                "path": "src/task_api.py",
                "content": (
                    "class TaskManager:\n"
                    "    def __init__(self):\n"
                    "        self.tasks = {}\n"
                    "    def create_task(self, title):\n"
                    "        task_id = str(len(self.tasks) + 1)\n"
                    "        task = {'id': task_id, 'title': title, 'status': 'pending'}\n"
                    "        self.tasks[task_id] = task\n"
                    "        return task\n"
                    "    def list_tasks(self):\n"
                    "        return list(self.tasks.values())\n"
                    "    def complete_task(self, task_id):\n"
                    "        if task_id in self.tasks:\n"
                    "            self.tasks[task_id]['status'] = 'completed'\n"
                    "            return self.tasks[task_id]\n"
                    "        return None\n"
                    "    def health(self):\n"
                    "        return {'status': 'ok'}\n"
                )
            },
            {
                "path": "test_tasks.py",
                "content": (
                    "from src.task_api import TaskManager\n"
                    "tm = TaskManager()\n"
                    "# 1. Create task\n"
                    "t1 = tm.create_task('Setup Database')\n"
                    "assert t1['status'] == 'pending'\n"
                    "# 2. List tasks\n"
                    "assert len(tm.list_tasks()) == 1\n"
                    "# 3. Complete task\n"
                    "t1_updated = tm.complete_task('1')\n"
                    "assert t1_updated['status'] == 'completed'\n"
                    "# 4. Health check\n"
                    "assert tm.health()['status'] == 'ok'\n"
                    "print('ALL TASK API TESTS PASSED')\n"
                )
            }
        ]

        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands=ExecutionCommands(
                install="python --version",
                build="python -m py_compile src/task_api.py",
                test="python test_tasks.py"
            )
        )

        dod = DefinitionOfDone(items=[
            DoDItem(id="AC-BUILD", description="Build cleanly", verification_type="build"),
            DoDItem(id="AC-TEST", description="Task API unit tests pass", verification_type="test"),
            DoDItem(id="AC-HEALTH", description="Health check endpoint operational", verification_type="health_check")
        ])

        start_time = time.time()
        service = RepairLoopService()
        
        runner = E2BSandboxRunner() if os.getenv("E2B_API_KEY") else LocalSubprocessSandboxRunner()
        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            self.project_a_id, files_run_a, plan, dod, problem_statement="Task Management API", custom_runner=runner
        ))
        elapsed = time.time() - start_time

        self.assertEqual(res.final_status, "VALIDATED")
        self.assertEqual(res.attempts_used, 1)
        self.assertEqual(len(res.repair_history), 0)
        
        print(f"[PASS] RUN A (Clean End-to-End Task API Execution) PASSED in {elapsed:.2f}s!")

    def test_run_b_defective_project_repair_execution(self):
        """RUN B: End-to-end execution of a Task Management API project with a defect (Expected: Attempt 1 FAIL -> Fix -> Attempt 2 PASS)."""
        files_run_b = [
            {"path": "requirements.txt", "content": ""},
            {
                "path": "src/task_api.py",
                "content": (
                    "class TaskManager:\n"
                    "    def __init__(self):\n"
                    "        self.tasks = {}\n"
                    "    def create_task(self, title):\n"
                    "        task_id = str(len(self.tasks) + 1)\n"
                    "        task = {'id': task_id, 'title': title, 'status': 'pending'}\n"
                    "        self.tasks[task_id] = task\n"
                    "        return task\n"
                    "    def list_tasks(self):\n"
                    "        return list(self.tasks.values())\n"
                    "    def complete_task(self, task_id):\n"
                    "        if task_id in self.tasks:\n"
                    "            self.tasks[task_id]['status'] = 'pending'  # DEFECT: sets pending instead of completed\n"
                    "            return self.tasks[task_id]\n"
                    "        return None\n"
                    "    def health(self):\n"
                    "        return {'status': 'ok'}\n"
                )
            },
            {
                "path": "test_tasks.py",
                "content": (
                    "from src.task_api import TaskManager\n"
                    "tm = TaskManager()\n"
                    "t1 = tm.create_task('Deploy API')\n"
                    "assert tm.complete_task('1')['status'] == 'completed', 'Task must be completed'\n"
                    "print('ALL TESTS PASSED')\n"
                )
            }
        ]

        plan = ExecutionPlan(
            project_type="python",
            executable=True,
            commands=ExecutionCommands(
                install="python --version",
                build="python -m py_compile src/task_api.py",
                test="python test_tasks.py"
            )
        )

        dod = DefinitionOfDone(items=[
            DoDItem(id="AC-TEST", description="Task completion unit tests pass", verification_type="test")
        ])

        start_time = time.time()
        service = RepairLoopService()
        
        runner = E2BSandboxRunner() if os.getenv("E2B_API_KEY") else LocalSubprocessSandboxRunner()
        res: FinalValidationResult = asyncio.run(service.run_repair_loop(
            self.project_b_id, files_run_b, plan, dod, problem_statement="Task Management API with Defect", custom_runner=runner
        ))
        elapsed = time.time() - start_time

        self.assertEqual(res.final_status, "VALIDATED")
        self.assertEqual(res.attempts_used, 2)
        self.assertEqual(len(res.repair_history), 1)
        self.assertEqual(res.repair_history[0].patch_status, "APPLIED")
        
        print(f"[PASS] RUN B (Defective Task API Auto-Repair & Re-Execution) PASSED in {elapsed:.2f}s!")


if __name__ == "__main__":
    unittest.main()
