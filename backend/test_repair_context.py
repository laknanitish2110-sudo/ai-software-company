import os
import sys
import shutil
import unittest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.execution_schema import (
    DefinitionOfDone,
    DoDItem,
    RepairContext,
    MissingFileError
)
from app.services.sandbox_runner import ExecutionResult, StageResult
from app.agents.qa import QAReport, QARepairInstructions
from app.services.repair_context_builder import (
    build_repair_context,
    MAX_AFFECTED_FILES,
    PROJECTS_DIR
)


class TestP21RepairContextFoundation(unittest.TestCase):

    def setUp(self):
        self.test_pid = "test_repair_ctx_pid_789"
        self.project_dir = PROJECTS_DIR / self.test_pid
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir, ignore_errors=True)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Write sample project files to disk
        (self.project_dir / "src").mkdir(exist_ok=True)
        (self.project_dir / "src/app.py").write_text("print('Hello App')", encoding="utf-8")
        (self.project_dir / "src/utils.py").write_text("def helper(): pass", encoding="utf-8")
        (self.project_dir / "file1.txt").write_text("Content 1", encoding="utf-8")
        (self.project_dir / "file2.txt").write_text("Content 2", encoding="utf-8")
        (self.project_dir / "file3.txt").write_text("Content 3", encoding="utf-8")
        (self.project_dir / "file4.txt").write_text("Content 4", encoding="utf-8")
        (self.project_dir / "file5.txt").write_text("Content 5", encoding="utf-8")
        (self.project_dir / "file6.txt").write_text("Content 6", encoding="utf-8")

        self.dod = DefinitionOfDone(items=[
            DoDItem(id="AC-1", description="Build cleanly", verification_type="build")
        ])
        self.exec_result = ExecutionResult(
            project_id=self.test_pid,
            overall_status="FAILED",
            failed_stage="BUILD",
            stages={"BUILD": StageResult(status="FAILED", exit_code=1, stderr_snippet="SyntaxError in src/app.py")}
        )

    def tearDown(self):
        if self.project_dir.exists():
            shutil.rmtree(self.project_dir, ignore_errors=True)

    def test_case_a_existing_affected_file(self):
        """CASE A: QA identifies an existing affected file -> RepairContext contains file content."""
        qa_report = QAReport(
            status="FAIL",
            severity="HIGH",
            failure_category="BUILD_FAILURE",
            affected_files=["src/app.py"]
        )

        ctx: RepairContext = build_repair_context(
            project_id=self.test_pid,
            qa_report=qa_report,
            exec_result=self.exec_result,
            dod=self.dod
        )

        self.assertIn("src/app.py", ctx.file_contents)
        self.assertEqual(ctx.file_contents["src/app.py"], "print('Hello App')")
        self.assertEqual(len(ctx.missing_files), 0)
        print("[PASS] CASE A: Existing affected file content included PASSED.")

    def test_case_b_nonexistent_file(self):
        """CASE B: QA identifies a nonexistent file -> Structured missing-file error."""
        qa_report = QAReport(
            status="FAIL",
            severity="HIGH",
            failure_category="BUILD_FAILURE",
            affected_files=["src/nonexistent_file.py"]
        )

        ctx: RepairContext = build_repair_context(
            project_id=self.test_pid,
            qa_report=qa_report,
            exec_result=self.exec_result,
            dod=self.dod
        )

        self.assertEqual(len(ctx.file_contents), 0)
        self.assertEqual(len(ctx.missing_files), 1)
        self.assertEqual(ctx.missing_files[0].path, "src/nonexistent_file.py")
        self.assertIn("does not exist", ctx.missing_files[0].error)
        self.assertFalse(ctx.missing_files[0].security_flag)
        print("[PASS] CASE B: Nonexistent file structured error PASSED.")

    def test_case_c_multiple_files_limit(self):
        """CASE C: QA identifies multiple files -> Only allowed/relevant files (up to max limit) are included."""
        qa_report = QAReport(
            status="FAIL",
            severity="HIGH",
            failure_category="BUILD_FAILURE",
            affected_files=["file1.txt", "file2.txt", "file3.txt", "file4.txt", "file5.txt", "file6.txt"]
        )

        ctx: RepairContext = build_repair_context(
            project_id=self.test_pid,
            qa_report=qa_report,
            exec_result=self.exec_result,
            dod=self.dod
        )

        self.assertLessEqual(len(ctx.file_contents), MAX_AFFECTED_FILES)
        self.assertEqual(len(ctx.file_contents), 5)
        self.assertNotIn("file6.txt", ctx.file_contents)
        print("[PASS] CASE C: Multiple files context size limit PASSED.")

    def test_case_d_path_traversal_rejection(self):
        """CASE D: Path traversal attempt -> Rejected with security flag."""
        qa_report = QAReport(
            status="FAIL",
            severity="HIGH",
            failure_category="BUILD_FAILURE",
            affected_files=["../../etc/passwd", "../outside.py"]
        )

        ctx: RepairContext = build_repair_context(
            project_id=self.test_pid,
            qa_report=qa_report,
            exec_result=self.exec_result,
            dod=self.dod
        )

        self.assertEqual(len(ctx.file_contents), 0)
        self.assertEqual(len(ctx.missing_files), 2)
        for missing in ctx.missing_files:
            self.assertTrue(missing.security_flag)
            self.assertIn("traversal", missing.error.lower())
        print("[PASS] CASE D: Path traversal rejection PASSED.")


if __name__ == "__main__":
    unittest.main()
