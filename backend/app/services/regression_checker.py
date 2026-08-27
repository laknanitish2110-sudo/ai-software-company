import re
import logging
from typing import List, Dict, Any, Optional

from app.models.execution_schema import (
    ExecutionBaseline,
    RegressionResult
)
from app.services.sandbox_runner import ExecutionResult, StageResult

logger = logging.getLogger(__name__)


class RegressionChecker:
    """
    Dedicated service for capturing execution baselines and comparing before/after execution states
    to enforce regression protection invariants.
    """
    def capture_baseline(self, exec_result: ExecutionResult) -> ExecutionBaseline:
        """Captures a structured ExecutionBaseline from an ExecutionResult."""
        if not exec_result:
            return ExecutionBaseline(overall_status="FAILED", failed_stage="SETUP")

        baseline = ExecutionBaseline(
            project_id=exec_result.project_id,
            overall_status=exec_result.overall_status,
            failed_stage=exec_result.failed_stage
        )

        for stage_name, stage_res in exec_result.stages.items():
            baseline.stage_statuses[stage_name] = stage_res.status
            stage_check = f"stage:{stage_name}"

            if stage_res.status == "PASSED":
                baseline.passed_checks.append(stage_check)
            elif stage_res.status == "FAILED":
                baseline.failed_checks.append(stage_check)

            # Parse test-level names from stdout/stderr snippets if available
            snippet = (stage_res.stdout_snippet or "") + " " + (stage_res.stderr_snippet or "")
            
            # Match unit test names (e.g., TEST-A, TEST-B, test_add, test_sub)
            test_matches = re.findall(r'\b(TEST\-[A-Z0-9_]+|test_[\w]+)\b', snippet)
            for test_name in set(test_matches):
                # If "PASSED" or "ok" or "✓" is near test_name in snippet
                test_pattern_pass = re.compile(rf'{re.escape(test_name)}.*?(?:PASSED|ok|✓|PASS)', re.IGNORECASE)
                test_pattern_fail = re.compile(rf'{re.escape(test_name)}.*?(?:FAILED|FAIL|ERROR|✗)', re.IGNORECASE)

                if test_pattern_pass.search(snippet) and not test_pattern_fail.search(snippet):
                    if test_name not in baseline.passed_checks:
                        baseline.passed_checks.append(test_name)
                elif test_pattern_fail.search(snippet):
                    if test_name not in baseline.failed_checks:
                        baseline.failed_checks.append(test_name)

        return baseline

    def evaluate_regression(
        self,
        baseline: ExecutionBaseline,
        post_result: ExecutionResult
    ) -> RegressionResult:
        """
        Compares BEFORE (baseline) vs AFTER (post_result) validation states.
        Enforces: A repair is acceptable ONLY IF original failure resolved AND zero regressions.
        """
        post_base = self.capture_baseline(post_result)
        result = RegressionResult()

        # 1. Identify fixed failures
        for check in baseline.failed_checks:
            if check in post_base.passed_checks:
                result.fixed_failures.append(check)
            elif check in post_base.failed_checks:
                result.unchanged_failures.append(check)

        # 2. Identify regressions (previously passing checks now failing or missing)
        for check in baseline.passed_checks:
            if check in post_base.failed_checks:
                result.regressions.append(check)
            elif check.startswith("stage:") and check not in post_base.passed_checks:
                # Stage that previously passed is now SKIPPED or FAILED
                result.regressions.append(check)

        # 3. Identify new failures
        for check in post_base.failed_checks:
            if check not in baseline.failed_checks and check not in result.regressions:
                result.new_failures.append(check)

        # 4. Apply Regression Decision Policy Rules
        if result.regressions:
            result.status = "REGRESSION"
            result.safe_to_accept = False
            result.reason = f"Regression detected: previously passing check(s) failed after repair: {result.regressions}"
            logger.warning(f"Regression detected for project {baseline.project_id}: {result.reason}")
            return result

        if post_result.overall_status == "FAILED" and post_result.failed_stage and baseline.stage_statuses.get(post_result.failed_stage) == "PASSED":
            result.status = "REGRESSION"
            result.safe_to_accept = False
            result.reason = f"Regression detected: stage '{post_result.failed_stage}' passed in baseline but failed after repair."
            logger.warning(f"Stage regression detected for project {baseline.project_id}: {result.reason}")
            return result

        if result.unchanged_failures and not result.fixed_failures:
            result.status = "REPAIR_FAILED"
            result.safe_to_accept = False
            result.reason = f"Repair failed: original failure(s) remain unresolved: {result.unchanged_failures}"
            return result

        if result.new_failures:
            result.status = "REGRESSION"
            result.safe_to_accept = False
            result.reason = f"Regression detected: repair introduced new failure(s): {result.new_failures}"
            return result

        if result.fixed_failures and not result.regressions and not result.new_failures:
            result.status = "SAFE_TO_ACCEPT"
            result.safe_to_accept = True
            result.reason = f"Repair successful and safe to accept: resolved {result.fixed_failures} with 0 regressions."
            return result

        # Fallback evaluation based on overall status
        if post_result.overall_status == "PASSED":
            result.status = "SAFE_TO_ACCEPT"
            result.safe_to_accept = True
            result.reason = "Post-repair execution passed cleanly."
        else:
            result.status = "REPAIR_FAILED"
            result.safe_to_accept = False
            result.reason = f"Post-repair execution failed at stage '{post_result.failed_stage}'."

        return result


def capture_baseline(exec_result: ExecutionResult) -> ExecutionBaseline:
    checker = RegressionChecker()
    return checker.capture_baseline(exec_result)


def compare_execution_baseline(
    baseline: ExecutionBaseline,
    post_result: ExecutionResult
) -> RegressionResult:
    checker = RegressionChecker()
    return checker.evaluate_regression(baseline, post_result)
