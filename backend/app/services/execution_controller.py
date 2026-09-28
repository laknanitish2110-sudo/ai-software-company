"""
Autonomous execution controller for AI employees.

Policy-driven state machine — each employee role gets its own execution
pipeline via ExecutionPolicy (see execution_policies.py):

  Atlas (Engineer): PLANNING → IMPLEMENTING → EXECUTING → OBSERVING → REPAIRING → TESTING → QA → DELIVERING
  Scout (Researcher): PLANNING → RESEARCHING → ANALYZING → SYNTHESIZING → QA → DELIVERING
  Arc (Architect): PLANNING → DESIGNING → EVALUATING → REFINING → QA → DELIVERING
  ... etc.

Key design decisions:
- Policy-driven: each role has its own states, transitions, and phase prompts
- Structured state transitions: LLM returns JSON with next_state + reason
- Persistent E2B sandbox: one sandbox lives across the entire execution
- Budget-limited: max iterations, tokens, and wall-clock time prevent runaway
- Observable: every iteration logged, progress events published via Redis
- Independent Sentinel QA: separate LLM call in clean context for verification
- Cost tracking: per-phase token tracking for billing and budget enforcement
"""

import json
import asyncio
import logging
import time
import os
from typing import Any

from app.services.execution_policies import (
    Phase, ExecutionPolicy, TERMINAL_PHASES,
    get_policy_for_role, get_valid_transitions, get_phase_prompt,
)

logger = logging.getLogger(__name__)

ExecutionState = Phase


class AutonomousExecutionController:
    """Drives a single autonomous execution to completion using role-specific policies."""

    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self._sandbox = None
        self._cancelled = False
        self._policy: ExecutionPolicy | None = None
        self._phase_costs: dict[str, int] = {}
        self._total_cost_tokens: int = 0
        self._last_sentinel_result: dict | None = None

    async def run(self):
        """Main entry point — runs the full autonomous loop."""
        from app.core.database import (
            get_autonomous_execution, update_autonomous_execution,
            add_execution_log, get_employee, update_employee,
        )

        execution = await get_autonomous_execution(self.execution_id)
        if not execution:
            logger.error(f"Execution {self.execution_id} not found")
            return

        employee = await get_employee(execution["employee_id"], execution["user_id"])
        if not employee:
            await update_autonomous_execution(self.execution_id, {
                "status": "failed", "error": "Employee not found",
            })
            return

        self._policy = get_policy_for_role(employee.get("role", ""))
        logger.info(f"Execution {self.execution_id}: using {self._policy.role} policy ({len(self._policy.phases)} phases)")

        from app.core.database import now_iso
        await update_autonomous_execution(self.execution_id, {
            "status": "running", "started_at": now_iso(),
        })
        await update_employee(employee["id"], execution["user_id"], {"status": "working"})

        try:
            from app.services.action_ledger import record_execution_start
            await record_execution_start(
                execution_id=self.execution_id,
                actor=employee.get("name", "Employee"),
                goal=execution["goal"],
                policy_name=self._policy.role,
            )
            await self._publish_progress("started", f"Starting autonomous execution: {execution['goal'][:100]}")
            await self._execute_loop(execution, employee)
        except asyncio.CancelledError:
            await self._handle_cancellation(execution)
        except Exception as e:
            logger.error(f"Execution {self.execution_id} crashed: {e}", exc_info=True)
            await update_autonomous_execution(self.execution_id, {
                "status": "failed", "error": str(e),
                "completed_at": now_iso(),
            })
        finally:
            await self._cleanup_sandbox()
            await update_employee(employee["id"], execution["user_id"], {"status": "idle"})

    async def cancel(self):
        self._cancelled = True

    async def _execute_loop(self, execution: dict, employee: dict):
        """The core state machine loop."""
        from app.core.database import (
            update_autonomous_execution, add_execution_log, now_iso,
        )
        from app.agents.engine import call_llm_with_fallback
        from app.services.tool_executor import (
            get_tools_for_employee, execute_tool,
            EMPLOYEE_ROLE_TO_ENGINE_ROLE,
        )

        state = Phase(execution.get("state", "PLANNING"))
        iteration = execution.get("iteration", 0)
        tokens_used = execution.get("tokens_used", 0)
        max_iterations = execution.get("max_iterations", 25)
        max_tokens = execution.get("max_tokens", 200000)
        max_time = execution.get("max_time_seconds", 600)
        start_time = time.time()
        plan_text = execution.get("plan", "")

        emp_config = employee.get("config") or {}
        tool_names = emp_config.get("default_tools") if isinstance(emp_config, dict) else None
        if not tool_names and employee.get("template_id"):
            from app.core.database import list_templates
            templates = await list_templates(active_only=True)
            tmpl = next((t for t in templates if t["id"] == employee["template_id"]), None)
            if tmpl:
                tool_names = tmpl.get("default_tools")

        employee_tools = get_tools_for_employee(tool_names)
        engine_role = EMPLOYEE_ROLE_TO_ENGINE_ROLE.get(employee["role"].lower(), "engineer")

        chat_messages = self._build_system_messages(employee, execution["goal"])

        while state not in TERMINAL_PHASES:
            if self._cancelled:
                state = Phase.CANCELLED
                break

            from app.core.database import get_autonomous_execution as _check_exec
            _current = await _check_exec(self.execution_id)
            if _current and _current.get("status") == "cancelled":
                state = Phase.CANCELLED
                break

            if iteration >= max_iterations:
                await self._fail(f"Budget exceeded: {iteration}/{max_iterations} iterations", execution)
                return
            if tokens_used >= max_tokens:
                await self._fail(f"Token budget exceeded: {tokens_used}/{max_tokens}", execution)
                return
            if time.time() - start_time > max_time:
                await self._fail(f"Time limit exceeded: {max_time}s", execution)
                return

            iteration += 1
            iter_start = time.time()

            phase_prompt = get_phase_prompt(self._policy, state)
            if state == Phase.PLANNING and plan_text:
                phase_prompt += f"\n\nPrevious plan:\n{plan_text}"

            valid_next = get_valid_transitions(self._policy, state)
            transition_names = [p.value for p in valid_next if p not in TERMINAL_PHASES]
            transition_instruction = (
                "\n\nWhen you are ready to transition, respond with a JSON block:\n"
                '```json\n{"next_state": "<STATE>", "confidence": 0.0-1.0, "reason": "..."}\n```\n'
                f"Valid next states: {', '.join(transition_names)}\n"
                "If you need to stay in the current phase, omit the JSON block."
            )

            chat_messages.append({"role": "user", "content": f"[PHASE: {state.value}]\n{phase_prompt}{transition_instruction}"})

            await self._publish_progress(
                "iteration",
                f"Iteration {iteration}: {state.value}",
                {"state": state.value, "iteration": iteration},
            )

            use_tools = state != Phase.PLANNING

            tool_iterations = 0
            max_tool_iterations = 10
            response_text = ""

            while tool_iterations < max_tool_iterations:
                tool_iterations += 1
                text, tool_calls = await call_llm_with_fallback(
                    messages=chat_messages,
                    role=engine_role,
                    temperature=0.4,
                    tools=employee_tools if use_tools else None,
                )

                est_tokens = (len(str(chat_messages)) + len(text or "")) // 4
                tokens_used += est_tokens
                phase_key = state.value
                self._phase_costs[phase_key] = self._phase_costs.get(phase_key, 0) + est_tokens
                self._total_cost_tokens = tokens_used

                if not tool_calls:
                    response_text = text or ""
                    chat_messages.append({"role": "assistant", "content": response_text})
                    break

                tc_msg = {"role": "assistant", "content": None, "tool_calls": tool_calls}
                chat_messages.append(tc_msg)

                for tc in tool_calls:
                    func_name = tc["function"]["name"]
                    try:
                        func_args = json.loads(tc["function"]["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        func_args = {}

                    tool_start = time.time()
                    result = await execute_tool(
                        tool_name=func_name,
                        arguments=func_args,
                        employee_id=employee["id"],
                        user_id=execution["user_id"],
                        project_id=execution.get("session_id"),
                    )
                    tool_ms = int((time.time() - tool_start) * 1000)

                    result_str = json.dumps(result)
                    if len(result_str) > 8000:
                        result_str = result_str[:8000] + "...(truncated)"

                    chat_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    })

                    try:
                        from app.services.action_ledger import record_tool_execution
                        tool_success = not (isinstance(result, dict) and result.get("error"))
                        await record_tool_execution(
                            execution_id=self.execution_id,
                            iteration=iteration,
                            phase=state.value,
                            actor=employee.get("name", "Employee"),
                            tool_name=func_name,
                            tool_input=json.dumps(func_args)[:500],
                            tool_output=result_str[:500],
                            success=tool_success,
                            duration_ms=tool_ms,
                        )
                    except Exception as le:
                        logger.debug(f"Ledger tool record: {le}")

                    try:
                        from app.services.state_truth import record_tool_claim
                        await record_tool_claim(
                            employee_id=employee["id"],
                            user_id=execution["user_id"],
                            execution_id=self.execution_id,
                            tool_name=func_name,
                            claim_key=f"{func_name}:{json.dumps(func_args)[:100]}",
                            claim_value=result_str[:2000],
                        )
                    except Exception as se:
                        logger.debug(f"State claim record: {se}")
            else:
                response_text = text or "Tool iteration limit reached."
                chat_messages.append({"role": "assistant", "content": response_text})

            iter_ms = int((time.time() - iter_start) * 1000)

            await add_execution_log(
                execution_id=self.execution_id,
                iteration=iteration,
                state=state.value,
                action=state.value.lower(),
                input_summary=phase_prompt[:200],
                output_summary=response_text[:500] if response_text else None,
                tokens_used=est_tokens if 'est_tokens' in dir() else 0,
                duration_ms=iter_ms,
                success=True,
            )

            try:
                from app.services.action_ledger import record_llm_reasoning
                await record_llm_reasoning(
                    execution_id=self.execution_id,
                    iteration=iteration,
                    phase=state.value,
                    actor=employee.get("name", "Employee"),
                    input_summary=phase_prompt[:300],
                    output_summary=response_text[:300] if response_text else None,
                    tokens_used=est_tokens if 'est_tokens' in dir() else 0,
                    duration_ms=iter_ms,
                )
            except Exception as le:
                logger.debug(f"Ledger reasoning record: {le}")

            if state == Phase.QA:
                sentinel_result = await self._run_sentinel_verification(execution, plan_text)
                self._last_sentinel_result = sentinel_result
                if sentinel_result and sentinel_result.get("verdict") == "FAIL":
                    issues_text = json.dumps(sentinel_result.get("issues", []), indent=2)
                    chat_messages.append({
                        "role": "user",
                        "content": (
                            f"[SENTINEL QA REVIEW — INDEPENDENT VERIFICATION]\n"
                            f"An independent reviewer found issues:\n{issues_text}\n\n"
                            f"Summary: {sentinel_result.get('summary', 'Issues found')}\n\n"
                            f"You must fix these issues before the work can be delivered."
                        ),
                    })
                    await add_execution_log(
                        execution_id=self.execution_id,
                        iteration=iteration,
                        state="SENTINEL_QA",
                        action="sentinel_fail",
                        input_summary="Independent Sentinel verification",
                        output_summary=sentinel_result.get("summary", "")[:500],
                        tokens_used=0,
                        duration_ms=0,
                        success=False,
                    )
                    try:
                        from app.services.action_ledger import record_sentinel_verdict
                        await record_sentinel_verdict(
                            execution_id=self.execution_id, iteration=iteration,
                            phase=state.value, actor=employee.get("name", "Employee"),
                            tier=sentinel_result.get("tiers_run", 1),
                            verdict="FAIL",
                            issues=sentinel_result.get("issues"),
                            tiers_run=sentinel_result.get("tiers_run", 1),
                            elapsed_ms=int(sentinel_result.get("elapsed_seconds", 0) * 1000),
                        )
                    except Exception as le:
                        logger.debug(f"Ledger sentinel record: {le}")
                    try:
                        from app.services.state_truth import reject_execution_claims
                        await reject_execution_claims(self.execution_id, reason="sentinel_fail")
                    except Exception as se:
                        logger.debug(f"State truth reject: {se}")
                    try:
                        from app.services.trust_chain import fail_chain_on_sentinel_fail
                        await fail_chain_on_sentinel_fail(self.execution_id)
                    except Exception as te:
                        logger.debug(f"Trust chain fail: {te}")
                    next_state = Phase.REPAIRING if Phase.REPAIRING in get_valid_transitions(self._policy, state) else Phase.FAILED
                elif sentinel_result and sentinel_result.get("verdict") == "PASS":
                    await add_execution_log(
                        execution_id=self.execution_id,
                        iteration=iteration,
                        state="SENTINEL_QA",
                        action="sentinel_pass",
                        input_summary="Independent Sentinel verification",
                        output_summary=sentinel_result.get("summary", "")[:500],
                        tokens_used=0,
                        duration_ms=0,
                        success=True,
                    )
                    try:
                        from app.services.action_ledger import record_sentinel_verdict
                        await record_sentinel_verdict(
                            execution_id=self.execution_id, iteration=iteration,
                            phase=state.value, actor=employee.get("name", "Employee"),
                            tier=sentinel_result.get("tiers_run", 1),
                            verdict="PASS",
                            issues=sentinel_result.get("issues"),
                            tiers_run=sentinel_result.get("tiers_run", 1),
                            elapsed_ms=int(sentinel_result.get("elapsed_seconds", 0) * 1000),
                        )
                    except Exception as le:
                        logger.debug(f"Ledger sentinel record: {le}")
                    try:
                        from app.services.state_truth import promote_execution_claims
                        await promote_execution_claims(self.execution_id, verified_by="sentinel")
                    except Exception as se:
                        logger.debug(f"State truth promote: {se}")
                    try:
                        from app.services.recovery_engine import save_checkpoint
                        await save_checkpoint(
                            execution_id=self.execution_id,
                            employee_id=employee["id"],
                            phase=state.value,
                            iteration=iteration,
                            checkpoint_type="sentinel_pass",
                        )
                    except Exception as ce:
                        logger.debug(f"Recovery checkpoint: {ce}")
                    try:
                        from app.services.trust_chain import verify_chain_on_sentinel_pass
                        await verify_chain_on_sentinel_pass(self.execution_id)
                    except Exception as te:
                        logger.debug(f"Trust chain verify: {te}")
                    next_state = self._determine_next_state(state, response_text, self._policy)
                else:
                    next_state = self._determine_next_state(state, response_text, self._policy)
            else:
                next_state = self._determine_next_state(state, response_text, self._policy)

            if state == Phase.PLANNING:
                plan_text = response_text
                await update_autonomous_execution(self.execution_id, {"plan": plan_text})

            await update_autonomous_execution(self.execution_id, {
                "state": next_state.value,
                "iteration": iteration,
                "tokens_used": tokens_used,
                "progress": json.dumps({
                    "state": next_state.value,
                    "iteration": iteration,
                    "tokens_used": tokens_used,
                    "elapsed_seconds": int(time.time() - start_time),
                    "phase_costs": self._phase_costs,
                    "policy": self._policy.role,
                }),
            })

            if next_state != state:
                try:
                    from app.services.action_ledger import record_phase_transition
                    parsed = self._parse_transition_json(response_text)
                    await record_phase_transition(
                        execution_id=self.execution_id,
                        iteration=iteration,
                        from_phase=state.value,
                        to_phase=next_state.value,
                        actor=employee.get("name", "Employee"),
                        reason=parsed.get("reason") if parsed else None,
                        confidence=parsed.get("confidence") if parsed else None,
                        tokens_used=est_tokens if 'est_tokens' in dir() else 0,
                        duration_ms=iter_ms,
                    )
                except Exception as le:
                    logger.debug(f"Ledger transition record: {le}")

            state = next_state

            if len(chat_messages) > 60:
                chat_messages = self._compact_messages(chat_messages)

        if state == Phase.COMPLETED:
            await self._complete(execution, response_text, iteration, tokens_used)
        elif state == Phase.CANCELLED:
            await self._handle_cancellation(execution)

    async def _run_sentinel_verification(self, execution: dict, plan_text: str) -> dict | None:
        """Run multi-tier independent Sentinel QA verification."""
        try:
            from app.core.database import get_db
            db = await get_db()
            try:
                cursor = await db.execute(
                    "SELECT * FROM execution_artifacts WHERE execution_id = ?",
                    (self.execution_id,),
                )
                artifact_rows = await cursor.fetchall()
            finally:
                await db.close()

            artifacts = [
                {
                    "title": row.get("title", ""),
                    "path": row.get("path", ""),
                    "content": row.get("content", ""),
                    "language": row.get("language", ""),
                }
                for row in artifact_rows
            ] if artifact_rows else []

            from app.core.database import get_employee
            employee = await get_employee(execution["employee_id"], execution["user_id"])
            employee_name = employee["name"] if employee else "AI Employee"
            employee_role = employee.get("role", "software engineer") if employee else "software engineer"

            goal_priority = "medium"
            try:
                from app.core.database import get_db as _gdb
                db2 = await _gdb()
                try:
                    cursor2 = await db2.execute(
                        "SELECT gt.id, g.priority FROM goal_tasks gt "
                        "JOIN goals g ON g.id = gt.goal_id "
                        "WHERE gt.execution_id = ?",
                        (self.execution_id,),
                    )
                    row = await cursor2.fetchone()
                    if row:
                        goal_priority = row.get("priority", "medium")
                finally:
                    await db2.close()
            except Exception:
                pass

            from app.services.sentinel_verifier import sentinel_verify
            result = await sentinel_verify(
                goal=execution["goal"],
                plan=plan_text,
                artifacts=artifacts,
                employee_name=employee_name,
                employee_role=employee_role,
                priority=goal_priority,
            )

            tiers_run = result.get("tiers_run", 1)
            elapsed = result.get("elapsed_seconds", 0)
            await self._publish_progress(
                "sentinel_qa",
                f"Sentinel verdict: {result.get('verdict', 'UNKNOWN')} ({tiers_run} tiers, {elapsed}s)",
                {"verdict": result},
            )

            return result
        except Exception as e:
            logger.error(f"Sentinel verification error: {e}")
            return None

    def _build_system_messages(self, employee: dict, goal: str) -> list[dict]:
        system_prompt = (
            f"You are {employee['name']}, a {employee['role']} at ForgeAI.\n"
        )
        if employee.get("persona"):
            system_prompt += f"\n{employee['persona']}\n"

        system_prompt += (
            "\nYou are running in AUTONOMOUS MODE. You must complete the following goal "
            "entirely on your own, without asking questions. Use your tools to complete "
            "the work thoroughly.\n\n"
            "IMPORTANT RULES:\n"
            "- Produce complete, working output — no placeholders or TODOs\n"
            "- When you encounter errors, analyze and fix them\n"
            "- Each phase has a specific purpose — follow the phase instructions\n"
            "- When ready to move to the next phase, respond with a JSON transition block:\n"
            '  ```json\n  {"next_state": "PHASE_NAME", "confidence": 0.0-1.0, "reason": "..."}\n  ```\n'
            "- The valid next states will be listed in each phase prompt\n"
            "- Your work will be independently reviewed by a QA verifier\n"
            f"\nGOAL: {goal}\n"
        )
        return [{"role": "system", "content": system_prompt}]

    def _determine_next_state(self, current: Phase, response: str, policy: ExecutionPolicy) -> Phase:
        """Parse structured JSON transition from LLM response, with string-matching fallback."""
        valid = get_valid_transitions(policy, current)
        non_terminal = [p for p in valid if p not in TERMINAL_PHASES]

        parsed = self._parse_transition_json(response)
        if parsed:
            requested = parsed.get("next_state", "").upper()
            for candidate in valid:
                if candidate.value == requested:
                    confidence = parsed.get("confidence", 0.5)
                    reason = parsed.get("reason", "")
                    logger.info(
                        f"Execution {self.execution_id}: {current.value} → {candidate.value} "
                        f"(confidence={confidence}, reason={reason[:80]})"
                    )
                    return candidate
            logger.warning(
                f"Execution {self.execution_id}: LLM requested '{requested}' "
                f"but valid transitions are {[p.value for p in valid]}"
            )

        return self._fallback_transition(current, response, policy)

    @staticmethod
    def _parse_transition_json(response: str) -> dict | None:
        """Extract a JSON transition block from the LLM response."""
        if not response:
            return None
        import re
        json_match = re.search(r'```json\s*\n?\s*(\{.*?\})\s*\n?\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        bare_match = re.search(r'\{"next_state"\s*:.*?\}', response, re.DOTALL)
        if bare_match:
            try:
                return json.loads(bare_match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _fallback_transition(self, current: Phase, response: str, policy: ExecutionPolicy) -> Phase:
        """String-matching fallback for when LLM doesn't return structured JSON."""
        valid = get_valid_transitions(policy, current)
        non_terminal = [p for p in valid if p not in TERMINAL_PHASES]
        response_upper = response.upper() if response else ""

        if current == Phase.PLANNING:
            return non_terminal[0] if non_terminal else Phase.FAILED

        if current == Phase.DELIVERING:
            return Phase.COMPLETED

        for candidate in non_terminal:
            if candidate.value in response_upper:
                return candidate

        if "DONE" in response_upper or "COMPLETE" in response_upper or "PASSED" in response_upper:
            forward = [p for p in non_terminal if p != current]
            if forward:
                return forward[0]

        if "FAIL" in response_upper or "ERROR" in response_upper:
            if Phase.REPAIRING in valid:
                return Phase.REPAIRING
            return Phase.FAILED

        if len(non_terminal) == 1:
            return non_terminal[0]

        forward = [p for p in non_terminal if p != current]
        return forward[0] if forward else (non_terminal[0] if non_terminal else Phase.FAILED)

    def _compact_messages(self, messages: list[dict]) -> list[dict]:
        """Keep system + last 40 messages to avoid context overflow."""
        system = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        return system + rest[-40:]

    async def _complete(self, execution: dict, result: str, iteration: int, tokens_used: int):
        from app.core.database import update_autonomous_execution, now_iso

        await update_autonomous_execution(self.execution_id, {
            "status": "completed",
            "state": Phase.COMPLETED.value,
            "result": result,
            "iteration": iteration,
            "tokens_used": tokens_used,
            "completed_at": now_iso(),
            "progress": json.dumps({
                "state": Phase.COMPLETED.value,
                "iteration": iteration,
                "tokens_used": tokens_used,
                "phase_costs": self._phase_costs,
                "policy": self._policy.role if self._policy else "unknown",
            }),
        })

        await self._collect_artifacts(execution)

        try:
            from app.services.action_ledger import record_execution_complete
            from app.core.database import list_execution_artifacts
            artifacts = await list_execution_artifacts(self.execution_id)
            await record_execution_complete(
                execution_id=self.execution_id,
                iteration=iteration,
                actor=execution.get("employee_id", "Employee"),
                final_state="COMPLETED",
                artifacts_count=len(artifacts),
                total_tokens=tokens_used,
            )
        except Exception as le:
            logger.debug(f"Ledger completion record: {le}")

        try:
            from app.services.verification_proof import generate_scorecard
            await generate_scorecard(
                execution_id=self.execution_id,
                user_id=execution["user_id"],
                employee_id=execution.get("employee_id"),
                goal=execution.get("goal"),
                sentinel_result=self._last_sentinel_result,
            )
        except Exception as se:
            logger.debug(f"Scorecard generation: {se}")

        try:
            from app.services.experience_compiler import extract_patterns, compile_procedures
            await extract_patterns(
                execution_id=self.execution_id,
                employee_id=execution.get("employee_id", ""),
                user_id=execution["user_id"],
                outcome="success",
                goal=execution.get("goal"),
            )
            await compile_procedures(execution.get("employee_id", ""), execution["user_id"])
        except Exception as xp:
            logger.debug(f"Experience compiler: {xp}")

        await self._publish_progress("completed", f"Execution completed in {iteration} iterations")

        from app.core.database import log_activity, get_employee
        employee = await get_employee(execution["employee_id"], execution["user_id"])
        if employee:
            await log_activity(
                user_id=execution["user_id"],
                event_type="autonomous_execution_completed",
                title=f"{employee['name']} completed: {execution['goal'][:80]}",
                employee_id=execution["employee_id"],
                employee_name=employee["name"],
                detail=result[:300] if result else None,
                metadata={"execution_id": self.execution_id, "iterations": iteration},
            )

    async def _fail(self, error: str, execution: dict):
        from app.core.database import update_autonomous_execution, now_iso

        logger.warning(f"Execution {self.execution_id} failed: {error}")
        await update_autonomous_execution(self.execution_id, {
            "status": "failed",
            "error": error,
            "completed_at": now_iso(),
        })

        try:
            from app.services.action_ledger import record_execution_complete
            await record_execution_complete(
                execution_id=self.execution_id,
                iteration=execution.get("iteration", 0),
                actor=execution.get("employee_id", "Employee"),
                final_state="FAILED",
                total_tokens=execution.get("tokens_used", 0),
            )
        except Exception as le:
            logger.debug(f"Ledger failure record: {le}")

        try:
            from app.services.recovery_engine import diagnose_failure, attempt_recovery
            diagnosis = await diagnose_failure(
                execution_id=self.execution_id,
                error=error,
                phase=execution.get("state"),
                iteration=execution.get("iteration"),
            )
            recovery = await attempt_recovery(self.execution_id, diagnosis)
            logger.info(
                f"Recovery for {self.execution_id}: strategy={recovery['strategy']} outcome={recovery['outcome']}"
            )
        except Exception as re_err:
            logger.debug(f"Recovery engine: {re_err}")

        try:
            from app.services.experience_compiler import extract_patterns, compile_procedures
            await extract_patterns(
                execution_id=self.execution_id,
                employee_id=execution.get("employee_id", ""),
                user_id=execution["user_id"],
                outcome="failure",
                goal=execution.get("goal"),
            )
            await compile_procedures(execution.get("employee_id", ""), execution["user_id"])
        except Exception as xp:
            logger.debug(f"Experience compiler on failure: {xp}")

        await self._publish_progress("failed", error)

    async def _handle_cancellation(self, execution: dict):
        from app.core.database import update_autonomous_execution, now_iso

        await update_autonomous_execution(self.execution_id, {
            "status": "cancelled",
            "state": Phase.CANCELLED.value,
            "completed_at": now_iso(),
        })
        await self._publish_progress("cancelled", "Execution cancelled by user")

    async def _collect_artifacts(self, execution: dict):
        """Collect all files written during execution as artifacts."""
        from app.core.artifact_store import LocalArtifactStore
        from app.core.database import add_execution_artifact

        workspace = f"workspace_{execution['employee_id']}"
        store = LocalArtifactStore()

        try:
            files = await store.list_files(workspace)
            for fpath in files:
                try:
                    content_bytes = await store.read_file(workspace, fpath)
                    content = content_bytes.decode("utf-8", errors="replace")
                    lang = _guess_language(fpath)
                    await add_execution_artifact(
                        execution_id=self.execution_id,
                        artifact_type="code",
                        title=fpath.split("/")[-1],
                        path=fpath,
                        content=content[:50000],
                        language=lang,
                    )
                except Exception as e:
                    logger.debug(f"Could not collect artifact {fpath}: {e}")
        except Exception as e:
            logger.debug(f"Could not list workspace files: {e}")

    async def _publish_progress(self, event_type: str, message: str, data: dict | None = None):
        """Publish progress event via Redis for real-time UI updates."""
        try:
            from app.services.redis_coordinator import redis_coordinator
            await redis_coordinator.publish_event(
                f"execution:{self.execution_id}",
                f"execution_{event_type}",
                {
                    "execution_id": self.execution_id,
                    "message": message,
                    **(data or {}),
                },
            )
        except Exception as e:
            logger.debug(f"Redis publish for execution progress: {e}")

    async def _cleanup_sandbox(self):
        """Clean up persistent E2B sandbox if one was created."""
        if self._sandbox:
            try:
                self._sandbox.kill()
            except Exception:
                pass
            self._sandbox = None


def _guess_language(path: str) -> str | None:
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "jsx", ".tsx": "tsx", ".html": "html", ".css": "css",
        ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".md": "markdown", ".sql": "sql", ".sh": "bash",
        ".rs": "rust", ".go": "go", ".java": "java",
    }
    for ext, lang in ext_map.items():
        if path.endswith(ext):
            return lang
    return None


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------

async def start_autonomous_execution(execution_id: str):
    """Enqueue an autonomous execution for the durable worker to pick up.

    The execution stays in 'pending' status — the execution_worker polls
    for pending executions, claims them via Redis SETNX, and runs them
    with heartbeat/timeout/retry. This survives process restarts.
    """
    from app.core.database import get_autonomous_execution
    execution = await get_autonomous_execution(execution_id)
    if not execution:
        logger.error(f"start_autonomous_execution: {execution_id} not found")
        return
    if execution["status"] != "pending":
        logger.warning(f"start_autonomous_execution: {execution_id} already {execution['status']}")
        return
    logger.info(f"Execution {execution_id} enqueued for worker pickup")


async def cancel_autonomous_execution(execution_id: str) -> bool:
    """Cancel a running autonomous execution by marking it in the DB."""
    from app.core.database import get_autonomous_execution, update_autonomous_execution, now_iso
    execution = await get_autonomous_execution(execution_id)
    if not execution:
        return False
    if execution["status"] in ("completed", "failed", "cancelled"):
        return False
    await update_autonomous_execution(execution_id, {
        "status": "cancelled",
        "error": "Cancelled by user",
        "completed_at": now_iso(),
    })
    return True
