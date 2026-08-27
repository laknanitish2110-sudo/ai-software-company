import os
import sys
import unittest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models.execution_schema import (
    DefinitionOfDone,
    DoDItem,
    RepairContext,
    PatchResult,
    FilePatch
)
from app.agents.qa import QAReport
from app.agents.fixer import (
    generate_targeted_patch,
    validate_patch,
    compute_patch_hash
)


class TestP22TargetedFixer(unittest.TestCase):

    def setUp(self):
        self.repair_ctx = RepairContext(
            project_id="test_fixer_pid_101",
            failed_stage="HEALTH_CHECK",
            failure_category="HEALTH_FAILURE",
            error_snippet="HTTP probe returned 404 for /health",
            affected_file_paths=["src/app.py"],
            file_contents={"src/app.py": "from fastapi import FastAPI\napp = FastAPI()\n"}
        )

    def test_case_a_simple_failing_project_patch_ready(self):
        """CASE A: Simple failing project -> Fixer returns PATCH_READY with correct affected file."""
        res: PatchResult = generate_targeted_patch(self.repair_ctx)

        self.assertEqual(res.status, "PATCH_READY")
        self.assertEqual(len(res.changes), 1)
        self.assertEqual(res.changes[0].path, "src/app.py")
        self.assertEqual(res.changes[0].action, "modify")
        self.assertEqual(len(res.validation_errors), 0)
        print("[PASS] CASE A: Simple failing project PATCH_READY PASSED.")

    def test_case_b_path_traversal_rejection(self):
        """CASE B: Fixer attempts ../secret.txt -> Patch rejected."""
        mock_patch = PatchResult(
            status="PATCH_READY",
            changes=[FilePatch(path="../secret.txt", action="modify", content="stolen content")]
        )

        res: PatchResult = validate_patch(mock_patch, self.repair_ctx)

        self.assertEqual(res.status, "PATCH_REJECTED")
        self.assertGreater(len(res.validation_errors), 0)
        self.assertIn("Path traversal", res.validation_errors[0])
        print("[PASS] CASE B: Path traversal attempt rejected PASSED.")

    def test_case_c_duplicate_file_paths_rejection(self):
        """CASE C: Fixer returns duplicate file paths -> Patch rejected."""
        mock_patch = PatchResult(
            status="PATCH_READY",
            changes=[
                FilePatch(path="src/app.py", action="modify", content="code 1"),
                FilePatch(path="src/app.py", action="modify", content="code 2")
            ]
        )

        res: PatchResult = validate_patch(mock_patch, self.repair_ctx)

        self.assertEqual(res.status, "PATCH_REJECTED")
        self.assertGreater(len(res.validation_errors), 0)
        self.assertIn("Duplicate target path", res.validation_errors[0])
        print("[PASS] CASE C: Duplicate file paths rejected PASSED.")

    def test_case_d_empty_changes_list_rejection(self):
        """CASE D: Fixer returns an empty changes list with PATCH_READY -> Patch rejected."""
        mock_patch = PatchResult(
            status="PATCH_READY",
            changes=[]
        )

        res: PatchResult = validate_patch(mock_patch, self.repair_ctx)

        self.assertEqual(res.status, "PATCH_REJECTED")
        self.assertGreater(len(res.validation_errors), 0)
        self.assertIn("requires at least 1 file change", res.validation_errors[0])
        print("[PASS] CASE D: Empty changes list rejected PASSED.")

    def test_case_e_unrelated_file_rejection(self):
        """CASE E: Fixer attempts to change an unrelated file -> Rejected by validation policy."""
        mock_patch = PatchResult(
            status="PATCH_READY",
            changes=[FilePatch(path="unrelated/other.py", action="modify", content="new code")]
        )

        res: PatchResult = validate_patch(mock_patch, self.repair_ctx)

        self.assertEqual(res.status, "PATCH_REJECTED")
        self.assertGreater(len(res.validation_errors), 0)
        self.assertIn("Unrelated file patch rejected", res.validation_errors[0])
        print("[PASS] CASE E: Unrelated file path rejected PASSED.")

    def test_case_f_previous_attempt_duplicate_patch_failure(self):
        """CASE F: Previous attempt already used identical patch and failed -> Fixer returns PREVIOUS_PATCH_FAILED."""
        changes = [FilePatch(path="src/app.py", action="modify", content="failed_patch_code()")]
        patch_hash = compute_patch_hash(changes)

        # Set up repair context with previous failed attempt
        self.repair_ctx.previous_attempts = [
            {"attempt": 1, "patch_hash": patch_hash, "status": "FAILED"}
        ]

        mock_patch = PatchResult(
            status="PATCH_READY",
            changes=changes
        )

        res: PatchResult = validate_patch(mock_patch, self.repair_ctx)

        self.assertEqual(res.status, "PREVIOUS_PATCH_FAILED")
        self.assertIn("previously failed", res.reason)
        print("[PASS] CASE F: Previous duplicate failed patch detected PASSED.")


if __name__ == "__main__":
    unittest.main()
