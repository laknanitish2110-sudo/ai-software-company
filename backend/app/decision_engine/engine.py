"""
Decision Engine — central decision layer for ARIA.

Wraps Jev/Jeff client with question definitions and confidence thresholds.
Falls back to existing logic when confidence is below threshold.
Logs all decisions for evaluation dataset building.
"""

import logging
import json
import asyncio
from typing import Optional
from dataclasses import asdict

from app.decision_engine.jev_client import decide, decide_multi, DecisionResult
from app.decision_engine import questions
from app.decision_engine import thresholds

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Centralized decision layer for ForgeAI pipeline and employee system."""

    async def classify_route(self, problem_statement: str) -> tuple[str, DecisionResult]:
        """Classify which pipeline route to use for a task.

        Returns (route_name, decision_result).
        If confidence is below threshold, falls back to keyword classifier.
        """
        state = f"User task description:\n{problem_statement}"
        result = await decide(state, questions.ROUTE_CLASSIFICATION)

        self._log_decision("route_classification", state, result)

        if result.above_threshold(thresholds.ROUTING_CONFIDENCE):
            return result.choice, result
        else:
            from app.services.task_router import classify_task
            fallback = classify_task(problem_statement)
            logger.info(f"Route decision below threshold ({result.confidence:.2f}), using keyword fallback: {fallback['suggested_route']}")
            return fallback["suggested_route"], result

    async def qa_gate(
        self,
        tests_total: int,
        tests_passed: int,
        tests_failed: int,
        failure_details: str = "",
        attempt_number: int = 1,
    ) -> tuple[str, DecisionResult]:
        """Decide whether to pass, repair, or escalate after QA.

        Returns (decision, result).
        """
        state = (
            f"Test Results:\n"
            f"  Total: {tests_total}\n"
            f"  Passed: {tests_passed}\n"
            f"  Failed: {tests_failed}\n"
            f"  Attempt: {attempt_number}/3\n"
        )
        if failure_details:
            state += f"\nFailure details:\n{failure_details[:500]}"

        result = await decide(state, questions.QA_GATE)
        self._log_decision("qa_gate", state, result)

        if result.above_threshold(thresholds.QA_CONFIDENCE):
            return result.choice, result
        return "repair", result

    async def repair_strategy(
        self,
        attempt_number: int,
        previous_attempts: list[str],
        current_failures: str,
        files_changed: int,
    ) -> tuple[str, DecisionResult]:
        """Decide repair strategy: continue, change approach, or escalate.

        Returns (strategy, result).
        """
        history = "\n".join(f"  Attempt {i+1}: {a}" for i, a in enumerate(previous_attempts))
        state = (
            f"Repair History:\n{history}\n\n"
            f"Current attempt: {attempt_number}/3\n"
            f"Files changed: {files_changed}\n"
            f"Current failures:\n{current_failures[:500]}"
        )

        result = await decide(state, questions.REPAIR_STRATEGY)
        self._log_decision("repair_strategy", state, result)

        if result.above_threshold(thresholds.REPAIR_CONFIDENCE):
            return result.choice, result
        return "continue_repair", result

    async def route_employee(self, user_message: str) -> tuple[str, DecisionResult]:
        """Route a user message to the best employee.

        Returns (employee_slug, result).
        """
        state = f"User request:\n{user_message}"
        result = await decide(state, questions.EMPLOYEE_ROUTING)
        self._log_decision("employee_routing", state, result)

        if result.above_threshold(thresholds.EMPLOYEE_ROUTING_CONFIDENCE):
            return result.choice, result
        return "atlas", result

    async def assess_task(self, problem_statement: str) -> dict[str, DecisionResult]:
        """Multi-question assessment of a task in one pass.

        Returns dict with route, difficulty, and human_review decisions.
        """
        state = f"Task description:\n{problem_statement}"
        results = await decide_multi(state, {
            "route": questions.ROUTE_CLASSIFICATION,
            "difficulty": questions.TASK_DIFFICULTY,
            "human_review": questions.HUMAN_REVIEW_NEEDED,
        })
        for name, result in results.items():
            self._log_decision(f"assess_{name}", state, result)
        return results

    def _log_decision(self, decision_type: str, state: str, result: DecisionResult,
                      project_id: str = None, employee_id: str = None):
        """Log decision to database for evaluation dataset building."""
        logger.info(
            f"DECISION [{decision_type}] "
            f"choice={result.choice} "
            f"confidence={result.confidence:.2f} "
            f"backend={result.backend} "
            f"latency={result.latency_ms:.0f}ms"
        )
        try:
            from app.core.database import log_decision
            asyncio.get_event_loop().create_task(
                log_decision(
                    decision_type=decision_type,
                    selected_choice=result.choice,
                    confidence=result.confidence,
                    backend=result.backend,
                    latency_ms=result.latency_ms,
                    project_id=project_id,
                    employee_id=employee_id,
                    input_context=state[:2000],
                    options=json.dumps(result.probabilities),
                )
            )
        except Exception as e:
            logger.debug(f"Decision persistence skipped: {e}")


decision_engine = DecisionEngine()
