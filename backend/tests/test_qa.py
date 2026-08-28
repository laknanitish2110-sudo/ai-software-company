import os
import sys
import unittest

from app.models.execution_schema import DefinitionOfDone, DoDItem, parse_or_convert_dod, ExecutionPlan
from app.services.sandbox_runner import ExecutionResult, StageResult
from app.agents.qa import evaluate_qa_results, QAReport


class TestP1QAImplementation(unittest.TestCase):

    def test_p1_1_dod_conversion(self):
        """P1.1: Verify acceptance_criteria conversion into structured Definition of Done."""
        ba_output = {
            "acceptance_criteria": [
                "Next.js build must compile cleanly",
                "Unit test suite passes",
                "HTTP health check endpoint returns 200 OK",
                "UI design looks clean and user-friendly"
            ]
        }
        dod: DefinitionOfDone = parse_or_convert_dod(ba_output)
        
        self.assertEqual(len(dod.items), 4)
        self.assertEqual(dod.items[0].verification_type, "build")
        self.assertEqual(dod.items[1].verification_type, "test")
        self.assertEqual(dod.items[2].verification_type, "health_check")
        self.assertEqual(dod.items[3].verification_type, "manual_review")
        print("[PASS] P1.1 Definition of Done schema conversion PASSED.")

    def test_p1_4_case_a_happy_path_pass(self):
        """P1.4 CASE A: Project satisfying all Definition of Done criteria -> QA = PASS."""
        dod = DefinitionOfDone(items=[
            DoDItem(id="AC-1", description="Build cleanly", verification_type="build"),
            DoDItem(id="AC-2", description="Unit tests pass", verification_type="test"),
            DoDItem(id="AC-3", description="Health check probe 200 OK", verification_type="health_check"),
        ])

        exec_result = ExecutionResult(
            project_id="proj_pass_123",
            overall_status="PASSED",
            duration_ms=1500,
            stages={
                "INSTALL": StageResult(status="PASSED", exit_code=0),
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="PASSED", exit_code=0),
                "START": StageResult(status="PASSED", exit_code=0),
                "HEALTH_CHECK": StageResult(status="PASSED", exit_code=0, stdout_snippet="HTTP 200"),
            }
        )

        qa_report: QAReport = evaluate_qa_results(dod, exec_result, problem_statement="Build a resume scanner")

        self.assertEqual(qa_report.status, "PASS")
        self.assertEqual(qa_report.severity, "LOW")
        self.assertEqual(qa_report.failure_category, "NONE")
        self.assertEqual(len(qa_report.failed_criteria), 0)
        self.assertEqual(qa_report.confidence, 1.0)
        print("[PASS] P1.4 CASE A (Happy Path PASS) PASSED.")

    def test_p1_4_case_b_failure_path_fail(self):
        """P1.4 CASE B: Project failing a criterion -> QA = FAIL with identified criterion and root cause."""
        dod = DefinitionOfDone(items=[
            DoDItem(id="AC-BUILD", description="Build cleanly", verification_type="build"),
            DoDItem(id="AC-TEST", description="Unit tests pass", verification_type="test"),
            DoDItem(id="AC-HEALTH", description="Health check probe 200 OK", verification_type="health_check"),
        ])

        exec_result = ExecutionResult(
            project_id="proj_fail_456",
            overall_status="FAILED",
            failed_stage="TEST",
            duration_ms=2200,
            stages={
                "INSTALL": StageResult(status="PASSED", exit_code=0),
                "BUILD": StageResult(status="PASSED", exit_code=0),
                "TEST": StageResult(status="FAILED", exit_code=1, stderr_snippet="AssertionError: assert 1 == 2"),
                "START": StageResult(status="SKIPPED"),
                "HEALTH_CHECK": StageResult(status="SKIPPED"),
            }
        )

        qa_report: QAReport = evaluate_qa_results(dod, exec_result, problem_statement="Build a resume scanner")

        self.assertEqual(qa_report.status, "FAIL")
        self.assertEqual(qa_report.severity, "HIGH")
        self.assertEqual(qa_report.failure_category, "TEST_FAILURE")
        self.assertIn("AC-TEST", qa_report.failed_criteria)
        self.assertIn("AssertionError", qa_report.root_cause)
        self.assertGreater(len(qa_report.repair_instructions.action_items), 0)
        print("[PASS] P1.4 CASE B (Failure Path FAIL) PASSED.")


if __name__ == "__main__":
    unittest.main()
