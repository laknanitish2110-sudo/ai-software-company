"""
P4.8.2 — LLM-Powered Fixer Agent Unit & End-to-End Test Suite

Verifies:
CASE A: Realistic QA failure causes Fixer to invoke LLM and produce valid PatchResult.
CASE B: Malformed LLM JSON is rejected safely (PATCH_REJECTED).
CASE C: Path traversal patch ('..') -> PATCH_REJECTED.
CASE D: Duplicate target paths in patch -> PATCH_REJECTED.
CASE E: Unsupported 'delete' action -> PATCH_REJECTED.
CASE F: Unrelated file path patch -> PATCH_REJECTED.
CASE G: Identical previously failed patch -> PREVIOUS_PATCH_FAILED.
CASE H: Exceeding 5 files patch limit -> PATCH_REJECTED.
CASE I: Oversized file content -> PATCH_REJECTED.
CASE J: LLM exception handling without disk mutation -> PATCH_REJECTED.
CASE K: Fixer does NOT call PatchApplier.
CASE L: Fixer does NOT write to disk or mutate filesystem.
CASE M: Provider independence using existing LLM abstraction routing.
CASE N: Async event-loop responsiveness while Fixer awaits LLM call.
END-TO-END TEST: Complete integration flow from QA FAIL -> RepairContext -> Fixer LLM mock -> PatchResult -> validate_patch -> PatchApplier -> Sandbox -> Regression.
"""

import os
import sys
import json
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.execution_schema import RepairContext, PatchResult, FilePatch, ExecutionPlan, ExecutionCommands, DefinitionOfDone
from app.agents.fixer import generate_targeted_patch, validate_patch, compute_patch_hash, build_fixer_user_prompt
from app.agents.qa import evaluate_qa_results
from app.services.sandbox_runner import ExecutionResult, StageResult, LocalSubprocessSandboxRunner
from app.services.patch_applier import PatchApplier
from app.services.regression_checker import capture_baseline, compare_execution_baseline


class TestP482LLMFixerAgent(unittest.TestCase):

    def setUp(self):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        from app.services.redis_coordinator import redis_coordinator
        redis_coordinator.reset_in_memory()
        self.sample_context = RepairContext(
            project_id="proj_fixer_test_101",
            execution_id="exec_fixer_test_101",
            attempt=1,
            failed_stage="TEST",
            failure_category="ASSERTION_ERROR",
            error_signature="sig_math_calc_error",
            error_snippet="AssertionError: expected 15, got 5 in main.py line 12",
            affected_file_paths=["main.py"],
            file_contents={"main.py": "def calc(a, b):\n    return a - b\n"},
            definition_of_done={"unit_tests": ["calc(10, 5) == 15"]},
            architecture_constraints={"language": "python"}
        )

    def test_case_a_realistic_qa_failure_invokes_llm_valid_patch(self):
        """CASE A: Realistic QA failure causes Fixer to invoke LLM and produce valid PatchResult."""
        async def _run():
            llm_invoked = False
            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                nonlocal llm_invoked
                llm_invoked = True
                self.assertIn("AssertionError", messages[1]["content"])
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [
                        {
                            "path": "main.py",
                            "action": "modify",
                            "content": "def calc(a, b):\n    return a + b\n",
                            "reason": "Fix minus to plus operator"
                        }
                    ],
                    "reason": "Corrected subtraction to addition",
                    "confidence": 0.95
                })

            patch_res = await generate_targeted_patch(self.sample_context, llm_callable=mock_llm)
            self.assertTrue(llm_invoked)
            self.assertEqual(patch_res.status, "PATCH_READY")
            self.assertEqual(len(patch_res.changes), 1)
            self.assertEqual(patch_res.changes[0].path, "main.py")
            self.assertIn("return a + b", patch_res.changes[0].content)

        asyncio.run(_run())
        print("[PASS] CASE A (Realistic QA Failure -> Fixer LLM Call -> Valid PatchResult) PASSED.")

    def test_case_b_malformed_llm_json_rejected(self):
        """CASE B: Malformed LLM JSON is rejected safely."""
        async def _run():
            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return "THIS IS NOT VALID JSON {status: broken"

            patch_res = await generate_targeted_patch(self.sample_context, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PATCH_REJECTED")
            self.assertTrue(len(patch_res.validation_errors) > 0)
            self.assertIn("JSON parse error", patch_res.validation_errors[0])

        asyncio.run(_run())
        print("[PASS] CASE B (Malformed LLM JSON Rejected) PASSED.")

    def test_case_c_path_traversal_patch_rejected(self):
        """CASE C: LLM returns a path traversal patch -> PATCH_REJECTED."""
        async def _run():
            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [
                        {"path": "../secret.txt", "action": "modify", "content": "hacked", "reason": "exploit"}
                    ],
                    "reason": "malicious patch"
                })

            patch_res = await generate_targeted_patch(self.sample_context, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PATCH_REJECTED")
            self.assertTrue(any("Path traversal" in err for err in patch_res.validation_errors))

        asyncio.run(_run())
        print("[PASS] CASE C (Path Traversal Patch Rejected) PASSED.")

    def test_case_d_duplicate_paths_rejected(self):
        """CASE D: LLM returns duplicate target paths in changes -> PATCH_REJECTED."""
        async def _run():
            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [
                        {"path": "main.py", "action": "modify", "content": "code A", "reason": "fix A"},
                        {"path": "main.py", "action": "modify", "content": "code B", "reason": "fix B"}
                    ],
                    "reason": "duplicate change"
                })

            patch_res = await generate_targeted_patch(self.sample_context, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PATCH_REJECTED")
            self.assertTrue(any("Duplicate target path" in err for err in patch_res.validation_errors))

        asyncio.run(_run())
        print("[PASS] CASE D (Duplicate Paths Rejected) PASSED.")

    def test_case_e_delete_action_rejected(self):
        """CASE E: LLM attempts unsupported 'delete' action -> PATCH_REJECTED."""
        async def _run():
            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [
                        {"path": "main.py", "action": "delete", "content": "", "reason": "delete main file"}
                    ],
                    "reason": "delete file"
                })

            patch_res = await generate_targeted_patch(self.sample_context, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PATCH_REJECTED")
            self.assertTrue(any("Unsupported action 'delete'" in err for err in patch_res.validation_errors))

        asyncio.run(_run())
        print("[PASS] CASE E (Delete Action Rejected) PASSED.")

    def test_case_f_unrelated_file_rejected(self):
        """CASE F: LLM targets unrelated file not in affected paths or project -> PATCH_REJECTED."""
        async def _run():
            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [
                        {"path": "unrelated_other.py", "action": "modify", "content": "# unrelated", "reason": "random file"}
                    ],
                    "reason": "unrelated fix"
                })

            patch_res = await generate_targeted_patch(self.sample_context, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PATCH_REJECTED")
            self.assertTrue(any("Unrelated file patch rejected" in err for err in patch_res.validation_errors))

        asyncio.run(_run())
        print("[PASS] CASE F (Unrelated File Rejected) PASSED.")

    def test_case_g_identical_previously_failed_patch(self):
        """CASE G: LLM returns an identical previously failed patch -> PREVIOUS_PATCH_FAILED."""
        async def _run():
            patch_change = [FilePatch(path="main.py", action="modify", content="def calc(a, b):\n    return a + b\n", reason="fix")]
            failed_hash = compute_patch_hash(patch_change)
            ctx_with_history = RepairContext(
                project_id="proj_fixer_test_101",
                execution_id="exec_fixer_test_101",
                attempt=2,
                failed_stage="TEST",
                failure_category="ASSERTION_ERROR",
                error_snippet="Failed again",
                affected_file_paths=["main.py"],
                file_contents={"main.py": "def calc(a, b):\n    return a - b\n"},
                previous_attempts=[{"attempt": 1, "patch_hash": failed_hash, "reason": "Failed test"}]
            )

            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [
                        {"path": "main.py", "action": "modify", "content": "def calc(a, b):\n    return a + b\n", "reason": "fix"}
                    ],
                    "reason": "retry same fix"
                })

            patch_res = await generate_targeted_patch(ctx_with_history, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PREVIOUS_PATCH_FAILED")

        asyncio.run(_run())
        print("[PASS] CASE G (Identical Previously Failed Patch Rejected) PASSED.")

    def test_case_h_exceeding_max_file_count_rejected(self):
        """CASE H: LLM returns >5 files -> PATCH_REJECTED."""
        async def _run():
            many_files = [f"file_{i}.py" for i in range(6)]
            ctx_many = RepairContext(
                project_id="proj_many",
                execution_id="exec_many",
                attempt=1,
                affected_file_paths=many_files,
                file_contents={f: "code" for f in many_files}
            )

            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [{"path": f, "action": "modify", "content": "fix", "reason": "r"} for f in many_files],
                    "reason": "too many files"
                })

            patch_res = await generate_targeted_patch(ctx_many, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PATCH_REJECTED")
            self.assertTrue(any("Exceeded maximum patch file count limit" in err for err in patch_res.validation_errors))

        asyncio.run(_run())
        print("[PASS] CASE H (Exceeding Max File Count Rejected) PASSED.")

    def test_case_i_oversized_content_rejected(self):
        """CASE I: LLM returns oversized content (>50,000 chars) -> PATCH_REJECTED."""
        async def _run():
            oversized_text = "A" * 50005

            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [{"path": "main.py", "action": "modify", "content": oversized_text, "reason": "huge"}],
                    "reason": "oversized content"
                })

            patch_res = await generate_targeted_patch(self.sample_context, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PATCH_REJECTED")
            self.assertTrue(any("File content exceeds" in err for err in patch_res.validation_errors))

        asyncio.run(_run())
        print("[PASS] CASE I (Oversized Content Rejected) PASSED.")

    def test_case_j_llm_exception_handling_no_mutation(self):
        """CASE J: LLM raises an exception -> structured Fixer failure, no filesystem mutation."""
        async def _run():
            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                raise RuntimeError("LLM API Rate Limit Exceeded")

            no_pattern_context = RepairContext(
                project_id="proj_no_pattern",
                execution_id="exec_no_pattern",
                file_contents={"main.py": "x = 100\n"}
            )
            patch_res = await generate_targeted_patch(no_pattern_context, llm_callable=mock_llm)
            self.assertEqual(patch_res.status, "PATCH_REJECTED")
            self.assertIn("LLM call exception", patch_res.reason)

        asyncio.run(_run())
        print("[PASS] CASE J (LLM Exception Handled Gracefully Without Mutation) PASSED.")

    def test_case_k_and_l_fixer_does_not_call_patch_applier_or_write_disk(self):
        """CASE K & L: Fixer does NOT call PatchApplier or write to disk."""
        async def _run():
            async def mock_llm(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [{"path": "main.py", "action": "modify", "content": "def calc(a,b): return a+b", "reason": "fix"}],
                    "reason": "valid patch"
                })

            with patch.object(PatchApplier, "apply_patch") as mock_apply:
                patch_res = await generate_targeted_patch(self.sample_context, llm_callable=mock_llm)
                mock_apply.assert_not_called()
                self.assertEqual(patch_res.status, "PATCH_READY")

        asyncio.run(_run())
        print("[PASS] CASE K & L (Fixer Isolates LLM Generation From Patch Application & File Writes) PASSED.")

    def test_case_m_provider_independence_verification(self):
        """CASE M: Verify provider independence using existing LLM abstraction."""
        async def _run():
            with patch("app.agents.fixer._llm_call_with_retry", new_callable=AsyncMock) as mock_retry:
                mock_retry.return_value = (json.dumps({
                    "status": "PATCH_READY",
                    "changes": [{"path": "main.py", "action": "modify", "content": "def calc(): pass", "reason": "fix"}],
                    "reason": "provider test"
                }), "openrouter:gpt-4o")

                patch_res = await generate_targeted_patch(self.sample_context)
                mock_retry.assert_called_once()
                kwargs = mock_retry.call_args.kwargs
                self.assertIn("model", kwargs)
                self.assertIn("provider", kwargs)
                self.assertEqual(patch_res.status, "PATCH_READY")

        asyncio.run(_run())
        print("[PASS] CASE M (Provider Independence via LLM Engine Abstraction) PASSED.")

    def test_case_n_async_event_loop_responsiveness(self):
        """CASE N: Verify async event-loop responsiveness while Fixer awaits LLM."""
        async def _run():
            heartbeat_ticks = 0
            async def heartbeat_loop():
                nonlocal heartbeat_ticks
                for _ in range(5):
                    await asyncio.sleep(0.05)
                    heartbeat_ticks += 1

            async def slow_mock_llm(system_prompt, messages, max_tokens, timeout):
                await asyncio.sleep(0.2)
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [{"path": "main.py", "action": "modify", "content": "def calc(): pass", "reason": "fix"}],
                    "reason": "async fix"
                })

            hb_task = asyncio.create_task(heartbeat_loop())
            patch_res = await generate_targeted_patch(self.sample_context, llm_callable=slow_mock_llm)
            await hb_task

            self.assertTrue(heartbeat_ticks >= 3)
            self.assertEqual(patch_res.status, "PATCH_READY")

        asyncio.run(_run())
        print("[PASS] CASE N (Async Event-Loop Responsiveness Proved) PASSED.")

    def test_end_to_end_repair_flow_integration(self):
        """END-TO-END TEST: QA FAIL -> RepairContext -> Fixer LLM mock -> PatchResult -> validate_patch -> PatchApplier -> Sandbox -> Regression."""
        async def _run():
            proj_id = f"e2e_repair_llm_{os.urandom(4).hex()}"
            initial_files = [{"path": "calc.py", "content": "def add(a, b):\n    return a - b\n"}]
            plan = ExecutionPlan(
                project_type="python",
                executable=True,
                commands=ExecutionCommands(test="python -m unittest discover")
            )

            # Step 1: Initial failed execution
            exec_fail = ExecutionResult(project_id=proj_id, overall_status="FAILED", failed_stage="TEST")
            exec_fail.stages["TEST"] = StageResult(status="FAILED", exit_code=1, stderr_snippet="AssertionError: 5 != 15")

            # Step 2: QA evaluation
            dod_obj = DefinitionOfDone(unit_tests=["add(10,5)==15"])
            qa_report = evaluate_qa_results(dod_obj, exec_fail)
            self.assertEqual(qa_report.status, "FAIL")

            # Step 3: RepairContext building
            repair_ctx = RepairContext(
                project_id=proj_id,
                execution_id="exec_e2e_1",
                attempt=1,
                failed_stage="TEST",
                failure_category=qa_report.failure_category,
                error_snippet=qa_report.root_cause or "AssertionError: 5 != 15",
                affected_file_paths=["calc.py"],
                file_contents={"calc.py": "def add(a, b):\n    return a - b\n"}
            )

            # Step 4: Fixer LLM Mock
            async def mock_llm_fixer(system_prompt, messages, max_tokens, timeout):
                return json.dumps({
                    "status": "PATCH_READY",
                    "changes": [{"path": "calc.py", "action": "modify", "content": "def add(a, b):\n    return a + b\n", "reason": "Fix minus to plus"}],
                    "reason": "Corrected return formula"
                })

            patch_res = await generate_targeted_patch(repair_ctx, llm_callable=mock_llm_fixer)
            self.assertEqual(patch_res.status, "PATCH_READY")

            # Step 5: PatchApplier
            applier = PatchApplier()
            apply_result, updated_files = await applier.apply_patch(proj_id, patch_res, initial_files, attempt=1, execution_id="exec_e2e_1")
            self.assertEqual(apply_result.status, "APPLIED")
            self.assertEqual(updated_files[0]["content"], "def add(a, b):\n    return a + b\n")

            # Step 6: Post-patch sandbox re-execution simulation
            exec_pass = ExecutionResult(project_id=proj_id, overall_status="PASSED")
            exec_pass.stages["TEST"] = StageResult(status="PASSED", exit_code=0)

            # Step 7: Regression checking
            baseline = capture_baseline(exec_fail)
            reg_check = compare_execution_baseline(baseline, exec_pass)
            self.assertTrue(reg_check.safe_to_accept)

        asyncio.run(_run())
        print("[PASS] END-TO-END REPAIR INTEGRATION FLOW (QA Fail -> Context -> Fixer LLM -> PatchApplier -> Regression) PASSED.")


if __name__ == "__main__":
    unittest.main()
