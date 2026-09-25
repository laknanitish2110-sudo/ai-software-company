import os
import json
import logging
import asyncio
import inspect
from typing import List, Dict, Any, Optional, Callable, Awaitable

from app.models.execution_schema import (
    ExecutionPlan,
    DefinitionOfDone,
    FinalValidationResult,
    RepairAttempt,
    RegressionResult,
    PatchResult
)
from app.services.sandbox_runner import (
    run_sandbox_execution,
    LocalSubprocessSandboxRunner,
    E2BSandboxRunner,
    ExecutionResult,
    StageResult
)
from app.agents.qa import evaluate_qa_results, QAReport, QARepairInstructions
from app.services.repair_context_builder import build_repair_context
from app.agents.fixer import generate_targeted_patch
from app.services.patch_applier import PatchApplier
from app.services.regression_checker import capture_baseline, compare_execution_baseline
from app.services.resource_budget import resource_budget, ResourceBudgetExceededError

logger = logging.getLogger(__name__)

# HARD CEILING CONSTANT — Never execute attempt 4
MAX_REPAIR_ATTEMPTS = 3

# Idempotency safeguard tracking active repair loops to prevent duplicate executions
_repair_lock = asyncio.Lock()
active_repair_loops = set()


class RepairLoopService:
    """
    Coordinates the bounded self-repair loop (max 3 attempts).
    Integrates SandboxRunner, QA, RepairContextBuilder, Fixer, PatchApplier, and RegressionChecker.
    """
    async def run_repair_loop(
        self,
        project_id: str,
        files: List[dict],
        plan: ExecutionPlan,
        dod: DefinitionOfDone,
        problem_statement: str = "",
        engineer_output: Optional[dict] = None,
        architect_output: Optional[dict] = None,
        ba_output: Optional[dict] = None,
        notify_cb: Optional[Callable[[str, dict], Awaitable[None]]] = None,
        custom_runner: Optional[Any] = None,
        execution_id: Optional[str] = None
    ) -> FinalValidationResult:
        
        # Idempotency check: prevent duplicate concurrent runs for the same project
        async with _repair_lock:
            if project_id in active_repair_loops:
                logger.warning(f"Repair loop already active for project {project_id}. Rejecting duplicate invocation.")
                return FinalValidationResult(
                    attempts_used=0,
                    final_status="VALIDATION_FAILED",
                    reason=f"Duplicate repair loop invocation rejected for project {project_id}."
                )
            active_repair_loops.add(project_id)

        try:
            current_files = [dict(f) for f in files] if isinstance(files, list) else []
            history: List[RepairAttempt] = []
            previous_attempts_history: List[dict] = []
            regression_history: List[dict] = []

            # FIND-01: Synthesize independent QA assertions (deterministic, before loop)
            from app.services.qa_assertion_synthesizer import synthesize_assertions
            independent_assertions, iqa_unavailable_reason = synthesize_assertions(
                ba_output or {}, architect_output or {}, plan
            )
            if not independent_assertions:
                logger.warning(f"IQA unavailable for project {project_id}: {iqa_unavailable_reason}")
                return FinalValidationResult(
                    attempts_used=0,
                    final_status="VALIDATION_FAILED",
                    reason=f"Independent QA unavailable: {iqa_unavailable_reason}"
                )

            baseline = None
            last_exec_result = None
            last_qa_report = None
            snapshot = None
            pre_patch_files = None

            for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
                # Hard ceiling verification
                assert attempt <= MAX_REPAIR_ATTEMPTS, f"Hard ceiling violated: attempt {attempt} > {MAX_REPAIR_ATTEMPTS}"

                # Correction 7: Cancellation check before starting any repair attempt
                if execution_id:
                    from app.services.redis_coordinator import redis_coordinator
                    from app.services.task_queue import ExecutionCancelledError
                    if await redis_coordinator.is_cancelled(execution_id):
                        logger.info(f"Cancellation requested at repair attempt {attempt} for execution {execution_id}. Halting repair loop.")
                        raise ExecutionCancelledError(f"Cancellation requested during repair loop at attempt {attempt} for execution {execution_id}")

                if attempt > 1:
                    try:
                        await resource_budget.check_repair_budget(project_id)
                        await resource_budget.record_repair_attempt(project_id)
                    except ResourceBudgetExceededError as budget_err:
                        logger.warning(f"Repair loop budget exceeded for project {project_id}: {budget_err}")
                        return FinalValidationResult(
                            attempts_used=attempt - 1,
                            final_status="REPAIR_FAILED",
                            reason=str(budget_err),
                            last_execution_result=last_exec_result,
                            last_qa_report=last_qa_report,
                            history=history
                        )

                logger.info(f"--- REPAIR LOOP ATTEMPT {attempt}/{MAX_REPAIR_ATTEMPTS} FOR PROJECT {project_id} ---")
                if notify_cb:
                    await notify_cb("agent_started", {
                        "role": "repair_loop",
                        "message": f"Executing Repair Loop Attempt {attempt}/{MAX_REPAIR_ATTEMPTS}..."
                    })

                # Step 1: Sandbox Execution
                exec_result = await run_sandbox_execution(project_id, current_files, plan, custom_runner=custom_runner, iqa_assertions=independent_assertions)

                last_exec_result = exec_result

                # Step 2: QA Evaluation against DoD
                qa_report: QAReport = evaluate_qa_results(dod, exec_result, problem_statement=problem_statement)
                last_qa_report = qa_report

                # FIND-01: Independent QA gating (constraints 1 & 2)
                # Engineer tests are regression evidence only — never sufficient for VALIDATED.
                # IQA must also PASS for VALIDATED status.
                if qa_report.status == "PASS":
                    iqa_data = getattr(exec_result, 'independent_qa_result', None)
                    if not iqa_data or iqa_data.get("status") != "PASS":
                        qa_report.status = "FAIL"
                        if iqa_data and iqa_data.get("status") == "FAIL":
                            qa_report.failure_category = "INDEPENDENT_QA_FAILURE"
                            qa_report.root_cause = iqa_data.get("reason", "Independent QA assertions failed")
                            qa_report.failed_criteria = [
                                r.get("assertion", {}).get("requirement_id", "IQA-?")
                                for r in iqa_data.get("results", [])
                                if not r.get("passed", True)
                            ]
                            qa_report.repair_instructions = QARepairInstructions(
                                summary="Fix API endpoints to satisfy independent QA assertions",
                                action_items=[
                                    f"Fix {r.get('assertion', {}).get('method', '?')} {r.get('assertion', {}).get('path', '?')}: {r.get('error', '?')}"
                                    for r in iqa_data.get("results", [])
                                    if not r.get("passed", True)
                                ][:5]
                            )
                        else:
                            qa_report.failure_category = "INDEPENDENT_QA_FAILURE"
                            qa_report.root_cause = "Independent QA execution did not produce valid results."

                # Step 3: Decision Engine interprets QA evidence
                # Jev runs BEFORE pass/fail branching so it can override deterministic QA
                jev_qa_decision = None
                try:
                    from app.decision_engine import decision_engine
                    jev_qa_decision, jev_qa_result = await decision_engine.qa_gate(
                        tests_total=getattr(exec_result, 'tests_run', 0),
                        tests_passed=getattr(exec_result, 'tests_passed', 0),
                        tests_failed=getattr(exec_result, 'tests_failed', 0),
                        failure_details=qa_report.root_cause or "",
                        attempt_number=attempt,
                    )
                    if jev_qa_result.above_threshold(0.85):
                        if jev_qa_decision == "escalate":
                            logger.info(f"Jev escalated project {project_id} (confidence={jev_qa_result.confidence:.2f})")
                            return FinalValidationResult(
                                attempts_used=attempt,
                                final_status="ESCALATED",
                                reason=f"Jev decision engine escalated: requires human judgment (confidence={jev_qa_result.confidence:.2f})",
                                final_execution_result=exec_result.model_dump() if hasattr(exec_result, "model_dump") else exec_result.dict(),
                                final_qa_report=qa_report.model_dump() if hasattr(qa_report, "model_dump") else qa_report.dict(),
                                repair_history=history,
                            )
                        if jev_qa_decision == "repair" and qa_report.status == "PASS":
                            logger.info(f"Jev overrode PASS → REPAIR for project {project_id} (confidence={jev_qa_result.confidence:.2f})")
                            qa_report.status = "FAIL"
                            qa_report.failure_category = "JEV_OVERRIDE"
                            qa_report.root_cause = f"Decision engine flagged issues despite passing deterministic QA (confidence={jev_qa_result.confidence:.2f})"
                except Exception as e:
                    logger.debug(f"Jev QA gate skipped: {e}")

                # Step 4: Baseline & Regression Evaluation
                if attempt == 1:
                    baseline = capture_baseline(exec_result)
                    if qa_report.status == "PASS":
                        logger.info(f"Project {project_id} passed cleanly on Attempt 1.")
                        return FinalValidationResult(
                            attempts_used=1,
                            final_status="VALIDATED",
                            final_execution_result=exec_result.model_dump() if hasattr(exec_result, "model_dump") else exec_result.dict(),
                            final_qa_report=qa_report.model_dump() if hasattr(qa_report, "model_dump") else qa_report.dict(),
                            final_files=[dict(f) for f in current_files],
                            repair_history=[],
                            reason="Project passed all Definition of Done criteria cleanly on Attempt 1.",
                            build_artifacts=getattr(exec_result, "build_artifacts", None),
                        )
                else:
                    # Post-repair comparison against baseline
                    reg_result = compare_execution_baseline(baseline, exec_result)
                    regression_history.append(reg_result.model_dump() if hasattr(reg_result, "model_dump") else reg_result.dict())

                    if not reg_result.safe_to_accept:
                        logger.warning(f"Attempt {attempt} failed regression check ({reg_result.status}): {reg_result.reason}. Rolling back.")
                        if snapshot and pre_patch_files is not None:
                            current_files = await PatchApplier().rollback_snapshot(project_id, snapshot, pre_patch_files)

                    if qa_report.status == "PASS" and reg_result.safe_to_accept:
                        logger.info(f"Project {project_id} repaired and validated on Attempt {attempt}.")
                        return FinalValidationResult(
                            attempts_used=attempt,
                            final_status="VALIDATED",
                            final_execution_result=exec_result.model_dump() if hasattr(exec_result, "model_dump") else exec_result.dict(),
                            final_qa_report=qa_report.model_dump() if hasattr(qa_report, "model_dump") else qa_report.dict(),
                            final_files=[dict(f) for f in current_files],
                            repair_history=history,
                            regression_results=regression_history,
                            reason=f"Project repaired and validated on Attempt {attempt}.",
                            build_artifacts=getattr(exec_result, "build_artifacts", None),
                        )

                # Step 4: Check if Attempt Limit Reached
                if attempt == MAX_REPAIR_ATTEMPTS:
                    logger.warning(f"Hard ceiling reached ({MAX_REPAIR_ATTEMPTS} attempts) for project {project_id}. Terminating repair loop.")
                    return FinalValidationResult(
                        attempts_used=MAX_REPAIR_ATTEMPTS,
                        final_status="VALIDATION_FAILED",
                        final_execution_result=exec_result.model_dump() if hasattr(exec_result, "model_dump") else exec_result.dict(),
                        final_qa_report=qa_report.model_dump() if hasattr(qa_report, "model_dump") else qa_report.dict(),
                        repair_history=history,
                        regression_results=regression_history,
                        reason=f"Reached maximum repair attempts limit ({MAX_REPAIR_ATTEMPTS}) without achieving full validation.",
                        final_files=current_files,
                    )

                # Step 5.5: Jev repair strategy decision
                try:
                    from app.decision_engine import decision_engine
                    strategy, strat_result = await decision_engine.repair_strategy(
                        attempt_number=attempt,
                        previous_attempts=[h.get("patch_hash", "unknown") for h in previous_attempts_history],
                        current_failures=qa_report.root_cause or "",
                        files_changed=len([f for f in current_files if f.get("modified")]),
                    )
                    if strat_result.above_threshold(0.80) and strategy == "escalate_human":
                        logger.info(f"Jev recommends escalation at attempt {attempt} (confidence={strat_result.confidence:.2f})")
                        return FinalValidationResult(
                            attempts_used=attempt,
                            final_status="ESCALATED",
                            reason=f"Jev repair strategy: escalate to human (confidence={strat_result.confidence:.2f})",
                            final_execution_result=exec_result.model_dump() if hasattr(exec_result, "model_dump") else exec_result.dict(),
                            final_qa_report=qa_report.model_dump() if hasattr(qa_report, "model_dump") else qa_report.dict(),
                            repair_history=history,
                        )
                except Exception as e:
                    logger.debug(f"Jev repair strategy skipped: {e}")

                # Step 5: Build Repair Context & Generate Targeted Patch
                repair_ctx = await build_repair_context(
                    project_id=project_id,
                    qa_report=qa_report,
                    exec_result=exec_result,
                    dod=dod,
                    engineer_output={"files": current_files},
                    architect_output=architect_output,
                    attempt=attempt,
                    previous_attempts=previous_attempts_history
                )

                patch_res_or_coro = generate_targeted_patch(repair_ctx)
                if inspect.isawaitable(patch_res_or_coro):
                    patch_res: PatchResult = await patch_res_or_coro
                else:
                    patch_res: PatchResult = patch_res_or_coro

                attempt_record = RepairAttempt(
                    attempt=attempt,
                    execution_id=exec_result.execution_id,
                    qa_status=qa_report.status,
                    failure_category=qa_report.failure_category,
                    patch_status=patch_res.status,
                    post_execution_status=exec_result.overall_status,
                    reason=patch_res.reason or qa_report.root_cause
                )

                if patch_res.status == "PATCH_READY" and patch_res.changes:
                    # Save patch hash in attempt history
                    from app.agents.fixer import compute_patch_hash
                    patch_hash = compute_patch_hash(patch_res.changes)
                    attempt_record.patch_hash = patch_hash
                    previous_attempts_history.append({"attempt": attempt, "patch_hash": patch_hash, "status": "FAILED"})

                    applier = PatchApplier()
                    pre_patch_files = [dict(f) for f in current_files]
                    snapshot = await applier.create_snapshot(project_id, current_files)

                    apply_res, updated_files = await applier.apply_patch(project_id, patch_res, current_files, attempt=attempt, execution_id=execution_id)

                    if apply_res.status == "APPLIED":
                        current_files = updated_files
                        attempt_record.patch_status = "APPLIED"
                    else:
                        attempt_record.patch_status = "REJECTED"
                        attempt_record.reason = f"Patch application rejected: {apply_res.errors}"

                history.append(attempt_record)

            return FinalValidationResult(
                attempts_used=MAX_REPAIR_ATTEMPTS,
                final_status="VALIDATION_FAILED",
                final_execution_result=last_exec_result.model_dump() if hasattr(last_exec_result, "model_dump") else None,
                final_qa_report=last_qa_report.model_dump() if hasattr(last_qa_report, "model_dump") else None,
                repair_history=history,
                regression_results=regression_history,
                reason="Max repair attempts exhausted.",
                final_files=current_files,
            )

        finally:
            active_repair_loops.discard(project_id)
