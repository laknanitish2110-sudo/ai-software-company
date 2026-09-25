"""
Autonomous execution controller for AI employees.

Drives a state-machine loop that enables an employee (starting with Atlas,
the Software Engineer) to autonomously complete multi-step coding tasks:

  PLANNING → IMPLEMENTING → EXECUTING → OBSERVING → REPAIRING → TESTING → QA → DELIVERING → COMPLETED

Key design decisions:
- Employee-agnostic: any employee can use this loop, Atlas proves it first
- Persistent E2B sandbox: one sandbox lives across the entire execution
- Budget-limited: max iterations, tokens, and wall-clock time prevent runaway
- Observable: every iteration logged, progress events published via Redis
- Sentinel QA gate: optionally delegates to Sentinel for quality check before delivery
"""

import json
import asyncio
import logging
import time
import os
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionState(str, Enum):
    PLANNING = "PLANNING"
    IMPLEMENTING = "IMPLEMENTING"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    REPAIRING = "REPAIRING"
    TESTING = "TESTING"
    QA = "QA"
    DELIVERING = "DELIVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TRANSITIONS = {
    ExecutionState.PLANNING: [ExecutionState.IMPLEMENTING, ExecutionState.FAILED],
    ExecutionState.IMPLEMENTING: [ExecutionState.EXECUTING, ExecutionState.FAILED],
    ExecutionState.EXECUTING: [ExecutionState.OBSERVING, ExecutionState.FAILED],
    ExecutionState.OBSERVING: [
        ExecutionState.REPAIRING,
        ExecutionState.TESTING,
        ExecutionState.IMPLEMENTING,
        ExecutionState.FAILED,
    ],
    ExecutionState.REPAIRING: [ExecutionState.EXECUTING, ExecutionState.FAILED],
    ExecutionState.TESTING: [
        ExecutionState.QA,
        ExecutionState.REPAIRING,
        ExecutionState.FAILED,
    ],
    ExecutionState.QA: [
        ExecutionState.DELIVERING,
        ExecutionState.REPAIRING,
        ExecutionState.FAILED,
    ],
    ExecutionState.DELIVERING: [ExecutionState.COMPLETED, ExecutionState.FAILED],
}


PHASE_PROMPTS = {
    ExecutionState.PLANNING: (
        "You are in PLANNING phase. Analyze the goal and create a concrete, step-by-step plan.\n"
        "Output a numbered list of implementation steps. Be specific about files, functions, and tests.\n"
        "End your plan with a clear summary of what you will build.\n"
        "Do NOT start coding yet — just plan."
    ),
    ExecutionState.IMPLEMENTING: (
        "You are in IMPLEMENTING phase. Write the code according to your plan.\n"
        "Use write_file to create each file. Use read_file if you need to check existing files.\n"
        "Implement ALL the code needed — models, logic, endpoints, config.\n"
        "When you're done writing all files, respond with DONE."
    ),
    ExecutionState.EXECUTING: (
        "You are in EXECUTING phase. Run the code you wrote to verify it works.\n"
        "Use run_code to execute the main entry point or start the application.\n"
        "If it needs packages installed, include them.\n"
        "Report the output exactly as it appears."
    ),
    ExecutionState.OBSERVING: (
        "You are in OBSERVING phase. Analyze the execution results.\n"
        "If there were errors, identify the root cause and what needs to be fixed.\n"
        "If execution succeeded, decide whether to run tests or proceed to QA.\n"
        "Respond with one of: NEEDS_REPAIR (if errors), RUN_TESTS (if code works), NEEDS_MORE_CODE (if incomplete)."
    ),
    ExecutionState.REPAIRING: (
        "You are in REPAIRING phase. Fix the issues identified in the previous phase.\n"
        "Read the failing files, identify the bug, and use write_file to fix them.\n"
        "When all fixes are applied, respond with DONE."
    ),
    ExecutionState.TESTING: (
        "You are in TESTING phase. Write and run tests for the code you built.\n"
        "Use write_file to create test files, then use run_code to execute them.\n"
        "If tests fail, report what failed. If tests pass, respond with TESTS_PASSED."
    ),
    ExecutionState.QA: (
        "You are in QA phase. Review the entire codebase you've built.\n"
        "List all files created. Check for: missing error handling, security issues,\n"
        "incomplete implementations, missing edge cases.\n"
        "If quality is acceptable, respond with QA_PASSED.\n"
        "If issues found, respond with QA_FAILED and list what needs fixing."
    ),
    ExecutionState.DELIVERING: (
        "You are in DELIVERING phase. Prepare a final summary of what was built.\n"
        "List all files created, key decisions made, and how to use the result.\n"
        "This summary will be shown to the user as the deliverable."
    ),
}


class AutonomousExecutionController:
    """Drives a single autonomous execution to completion."""

    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self._sandbox = None
        self._cancelled = False

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

        from app.core.database import now_iso
        await update_autonomous_execution(self.execution_id, {
            "status": "running", "started_at": now_iso(),
        })
        await update_employee(employee["id"], execution["user_id"], {"status": "working"})

        try:
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

        state = ExecutionState(execution.get("state", "PLANNING"))
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

        while state not in (ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED):
            if self._cancelled:
                state = ExecutionState.CANCELLED
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

            phase_prompt = PHASE_PROMPTS.get(state, "")
            if state == ExecutionState.PLANNING and plan_text:
                phase_prompt += f"\n\nPrevious plan:\n{plan_text}"

            chat_messages.append({"role": "user", "content": f"[PHASE: {state.value}]\n{phase_prompt}"})

            await self._publish_progress(
                "iteration",
                f"Iteration {iteration}: {state.value}",
                {"state": state.value, "iteration": iteration},
            )

            use_tools = state in (
                ExecutionState.IMPLEMENTING, ExecutionState.EXECUTING,
                ExecutionState.REPAIRING, ExecutionState.TESTING,
                ExecutionState.QA, ExecutionState.DELIVERING,
            )

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

                    result = await execute_tool(
                        tool_name=func_name,
                        arguments=func_args,
                        employee_id=employee["id"],
                        user_id=execution["user_id"],
                        project_id=execution.get("session_id"),
                    )

                    result_str = json.dumps(result)
                    if len(result_str) > 8000:
                        result_str = result_str[:8000] + "...(truncated)"

                    chat_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str,
                    })
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

            next_state = self._determine_next_state(state, response_text)

            if state == ExecutionState.PLANNING:
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
                }),
            })

            state = next_state

            if len(chat_messages) > 60:
                chat_messages = self._compact_messages(chat_messages)

        if state == ExecutionState.COMPLETED:
            await self._complete(execution, response_text, iteration, tokens_used)
        elif state == ExecutionState.CANCELLED:
            await self._handle_cancellation(execution)

    def _build_system_messages(self, employee: dict, goal: str) -> list[dict]:
        system_prompt = (
            f"You are {employee['name']}, a {employee['role']} at ForgeAI.\n"
        )
        if employee.get("persona"):
            system_prompt += f"\n{employee['persona']}\n"

        system_prompt += (
            "\nYou are running in AUTONOMOUS MODE. You must complete the following goal "
            "entirely on your own, without asking questions. Use your tools to write code, "
            "execute it, fix errors, and test it.\n\n"
            "IMPORTANT RULES:\n"
            "- Write complete, working code — no placeholders or TODOs\n"
            "- When you encounter errors, analyze and fix them\n"
            "- Write tests and make sure they pass\n"
            "- Each phase has a specific purpose — follow the phase instructions\n"
            "- Respond with the phase transition keywords when ready to move on\n"
            f"\nGOAL: {goal}\n"
        )
        return [{"role": "system", "content": system_prompt}]

    def _determine_next_state(self, current: ExecutionState, response: str) -> ExecutionState:
        """Parse the LLM response to determine the next state transition."""
        response_upper = response.upper() if response else ""

        if current == ExecutionState.PLANNING:
            return ExecutionState.IMPLEMENTING

        elif current == ExecutionState.IMPLEMENTING:
            if "DONE" in response_upper:
                return ExecutionState.EXECUTING
            return ExecutionState.IMPLEMENTING

        elif current == ExecutionState.EXECUTING:
            return ExecutionState.OBSERVING

        elif current == ExecutionState.OBSERVING:
            if "NEEDS_REPAIR" in response_upper:
                return ExecutionState.REPAIRING
            elif "NEEDS_MORE_CODE" in response_upper:
                return ExecutionState.IMPLEMENTING
            elif "RUN_TESTS" in response_upper or "TESTS" in response_upper:
                return ExecutionState.TESTING
            return ExecutionState.TESTING

        elif current == ExecutionState.REPAIRING:
            if "DONE" in response_upper:
                return ExecutionState.EXECUTING
            return ExecutionState.REPAIRING

        elif current == ExecutionState.TESTING:
            if "TESTS_PASSED" in response_upper or "ALL TESTS PASS" in response_upper:
                return ExecutionState.QA
            elif "FAIL" in response_upper:
                return ExecutionState.REPAIRING
            return ExecutionState.QA

        elif current == ExecutionState.QA:
            if "QA_PASSED" in response_upper or "QUALITY" in response_upper and "ACCEPTABLE" in response_upper:
                return ExecutionState.DELIVERING
            elif "QA_FAILED" in response_upper:
                return ExecutionState.REPAIRING
            return ExecutionState.DELIVERING

        elif current == ExecutionState.DELIVERING:
            return ExecutionState.COMPLETED

        return ExecutionState.FAILED

    def _compact_messages(self, messages: list[dict]) -> list[dict]:
        """Keep system + last 40 messages to avoid context overflow."""
        system = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        return system + rest[-40:]

    async def _complete(self, execution: dict, result: str, iteration: int, tokens_used: int):
        from app.core.database import update_autonomous_execution, now_iso

        await update_autonomous_execution(self.execution_id, {
            "status": "completed",
            "state": ExecutionState.COMPLETED.value,
            "result": result,
            "iteration": iteration,
            "tokens_used": tokens_used,
            "completed_at": now_iso(),
        })

        await self._collect_artifacts(execution)
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
        await self._publish_progress("failed", error)

    async def _handle_cancellation(self, execution: dict):
        from app.core.database import update_autonomous_execution, now_iso

        await update_autonomous_execution(self.execution_id, {
            "status": "cancelled",
            "state": ExecutionState.CANCELLED.value,
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

_active_executions: dict[str, AutonomousExecutionController] = {}


async def start_autonomous_execution(execution_id: str) -> AutonomousExecutionController:
    """Start an autonomous execution in the background. Returns the controller."""
    controller = AutonomousExecutionController(execution_id)
    _active_executions[execution_id] = controller

    async def _run_and_cleanup():
        try:
            await controller.run()
        finally:
            _active_executions.pop(execution_id, None)

    asyncio.create_task(_run_and_cleanup())
    return controller


async def cancel_autonomous_execution(execution_id: str) -> bool:
    """Cancel a running autonomous execution."""
    controller = _active_executions.get(execution_id)
    if controller:
        await controller.cancel()
        return True
    return False


def get_active_execution(execution_id: str) -> AutonomousExecutionController | None:
    return _active_executions.get(execution_id)
