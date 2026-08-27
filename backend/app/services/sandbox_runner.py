import os
import sys
import time
import json
import uuid
import hashlib
import asyncio
import logging
import subprocess
import shutil
import tempfile
from typing import Dict, Any, Optional, List
import httpx
from pydantic import BaseModel, Field

from app.models.execution_schema import ExecutionPlan, ExecutionCommands, HealthCheckSpec
from app.core.config import get_environment, get_sandbox_mode, validate_sandbox_config

logger = logging.getLogger(__name__)

# Max log snippet size to prevent context window bloat
MAX_LOG_SIZE = 2000


class SandboxUnavailableError(Exception):
    """Raised when cloud sandbox is unavailable and local host execution is forbidden."""
    pass


class StageResult(BaseModel):
    status: str = "SKIPPED"  # PASSED, FAILED, SKIPPED, TIMEOUT
    exit_code: Optional[int] = None
    duration_ms: int = 0
    stdout_snippet: str = ""
    stderr_snippet: str = ""


class ExecutionResult(BaseModel):
    project_id: str
    execution_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    overall_status: str = "FAILED"  # PASSED, FAILED, SKIPPED
    failed_stage: Optional[str] = None
    duration_ms: int = 0
    error_signature: Optional[str] = None
    stages: Dict[str, StageResult] = Field(default_factory=lambda: {
        "SANDBOX_INIT": StageResult(),
        "INSTALL": StageResult(),
        "BUILD": StageResult(),
        "TEST": StageResult(),
        "START": StageResult(),
        "HEALTH_CHECK": StageResult(),
    })
    environment_used: Dict[str, str] = Field(default_factory=dict)


def _truncate_log(text: str, max_size: int = MAX_LOG_SIZE) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_size:
        return text
    half = max_size // 2
    return text[:half] + f"\n... [truncated {len(text) - max_size} chars] ...\n" + text[-half:]


def _generate_error_signature(failed_stage: str, stderr: str) -> str:
    first_lines = "\n".join([line for line in stderr.split("\n") if line.strip()][:5])
    raw = f"{failed_stage}:{first_lines}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


class BaseSandboxRunner:
    async def execute(self, project_id: str, files: List[dict], plan: ExecutionPlan) -> ExecutionResult:
        raise NotImplementedError


class LocalSubprocessSandboxRunner(BaseSandboxRunner):
    """
    Isolated local temporary directory runner for local development / testing ONLY.
    Requires SANDBOX_MODE=local_dev and ENVIRONMENT != production.
    """
    async def execute(self, project_id: str, files: List[dict], plan: ExecutionPlan) -> ExecutionResult:
        validate_sandbox_config()
        if get_sandbox_mode() != "local_dev":
            raise SandboxUnavailableError(
                "LocalSubprocessSandboxRunner is disabled. Set SANDBOX_MODE=local_dev in development to enable."
            )
        if get_environment() == "production":
            raise SandboxUnavailableError(
                "Security Violation: LocalSubprocessSandboxRunner is strictly forbidden in production."
            )

        start_time = time.time()
        result = ExecutionResult(project_id=project_id)
        result.environment_used = {"runner": "local_subprocess", "project_type": plan.project_type}

        if not plan.executable or not files:
            result.overall_status = "SKIPPED"
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        temp_dir = tempfile.mkdtemp(prefix=f"sandbox_{project_id}_")
        bg_process = None

        try:
            # 1. Write files into temporary directory
            for f in files:
                if not isinstance(f, dict):
                    continue
                rel_path = f.get("path", "").lstrip("/").lstrip("\\")
                content = f.get("content", "")
                if rel_path and content:
                    full_p = os.path.join(temp_dir, rel_path)
                    os.makedirs(os.path.dirname(full_p), exist_ok=True)
                    with open(full_p, "w", encoding="utf-8") as out_f:
                        out_f.write(content)

            cmds = plan.commands
            stages_to_run = [
                ("INSTALL", cmds.install, 120),
                ("BUILD", cmds.build, 60),
                ("TEST", cmds.test, 60),
                ("START", cmds.start, 20),
                ("HEALTH_CHECK", cmds.health_check, 15),
            ]

            overall_failed = False

            for stage_name, cmd_spec, timeout in stages_to_run:
                if overall_failed:
                    result.stages[stage_name] = StageResult(status="SKIPPED")
                    continue

                if stage_name == "HEALTH_CHECK" and isinstance(cmd_spec, HealthCheckSpec):
                    hc_start = time.time()
                    hc_spec: HealthCheckSpec = cmd_spec
                    url = f"http://127.0.0.1:{hc_spec.port}{hc_spec.path}"
                    
                    passed = False
                    last_err = ""
                    for attempt in range(5):
                        await asyncio.sleep(1)
                        try:
                            async with httpx.AsyncClient(timeout=3) as client:
                                resp = await client.get(url)
                                if resp.status_code == hc_spec.expected_status or resp.status_code in (200, 201, 204, 301, 302, 404):
                                    passed = True
                                    last_err = f"HTTP {resp.status_code}"
                                    break
                                else:
                                    last_err = f"HTTP {resp.status_code} != expected {hc_spec.expected_status}"
                        except Exception as e:
                            last_err = str(e)

                    duration = int((time.time() - hc_start) * 1000)
                    if passed:
                        result.stages[stage_name] = StageResult(
                            status="PASSED", exit_code=0, duration_ms=duration, stdout_snippet=f"Probed {url} -> {last_err}"
                        )
                    else:
                        overall_failed = True
                        result.failed_stage = stage_name
                        result.stages[stage_name] = StageResult(
                            status="FAILED", exit_code=1, duration_ms=duration, stderr_snippet=f"Health probe to {url} failed: {last_err}"
                        )
                        result.error_signature = _generate_error_signature(stage_name, last_err)

                elif stage_name == "START" and cmd_spec:
                    st_start = time.time()
                    try:
                        bg_process = subprocess.Popen(
                            cmd_spec,
                            shell=True,
                            cwd=temp_dir,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env={**os.environ, **plan.environment.env_vars}
                        )
                        await asyncio.sleep(2)
                        ret = bg_process.poll()
                        duration = int((time.time() - st_start) * 1000)
                        if ret is not None and ret != 0:
                            stderr_out = bg_process.stderr.read().decode(errors="ignore") if bg_process.stderr else ""
                            overall_failed = True
                            result.failed_stage = stage_name
                            result.stages[stage_name] = StageResult(
                                status="FAILED", exit_code=ret, duration_ms=duration, stderr_snippet=_truncate_log(stderr_out)
                            )
                            result.error_signature = _generate_error_signature(stage_name, stderr_out)
                        else:
                            result.stages[stage_name] = StageResult(
                                status="PASSED", exit_code=0, duration_ms=duration, stdout_snippet=f"Process started in background: {cmd_spec}"
                            )
                    except Exception as e:
                        overall_failed = True
                        result.failed_stage = stage_name
                        result.stages[stage_name] = StageResult(
                            status="FAILED", exit_code=1, duration_ms=int((time.time() - st_start) * 1000), stderr_snippet=str(e)
                        )
                        result.error_signature = _generate_error_signature(stage_name, str(e))

                elif cmd_spec and isinstance(cmd_spec, str):
                    st_start = time.time()
                    try:
                        proc = await asyncio.create_subprocess_shell(
                            cmd_spec,
                            cwd=temp_dir,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            env={**os.environ, **plan.environment.env_vars}
                        )
                        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                        duration = int((time.time() - st_start) * 1000)
                        stdout_str = stdout_b.decode(errors="ignore") if stdout_b else ""
                        stderr_str = stderr_b.decode(errors="ignore") if stderr_b else ""

                        if proc.returncode == 0:
                            result.stages[stage_name] = StageResult(
                                status="PASSED", exit_code=0, duration_ms=duration, stdout_snippet=_truncate_log(stdout_str)
                            )
                        else:
                            overall_failed = True
                            result.failed_stage = stage_name
                            result.stages[stage_name] = StageResult(
                                status="FAILED", exit_code=proc.returncode, duration_ms=duration,
                                stdout_snippet=_truncate_log(stdout_str), stderr_snippet=_truncate_log(stderr_str)
                            )
                            result.error_signature = _generate_error_signature(stage_name, stderr_str or stdout_str)
                    except asyncio.TimeoutError:
                        overall_failed = True
                        result.failed_stage = stage_name
                        result.stages[stage_name] = StageResult(
                            status="TIMEOUT", exit_code=124, duration_ms=timeout * 1000, stderr_snippet=f"Stage {stage_name} timed out after {timeout}s"
                        )
                        result.error_signature = _generate_error_signature(stage_name, "Timeout")
                    except Exception as e:
                        overall_failed = True
                        result.failed_stage = stage_name
                        result.stages[stage_name] = StageResult(
                            status="FAILED", exit_code=1, duration_ms=int((time.time() - st_start) * 1000), stderr_snippet=str(e)
                        )
                        result.error_signature = _generate_error_signature(stage_name, str(e))
                else:
                    result.stages[stage_name] = StageResult(status="SKIPPED")

            if not overall_failed:
                result.overall_status = "PASSED"

        finally:
            if bg_process:
                try:
                    if bg_process.stdout:
                        bg_process.stdout.close()
                    if bg_process.stderr:
                        bg_process.stderr.close()
                    bg_process.terminate()
                    bg_process.wait(timeout=2)
                except Exception:
                    pass
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result


class E2BSandboxRunner(BaseSandboxRunner):
    """
    Hardware Firecracker microVM execution runner using E2B API SDK.
    Never falls back to host execution.
    """
    async def execute(self, project_id: str, files: List[dict], plan: ExecutionPlan) -> ExecutionResult:
        e2b_key = os.getenv("E2B_API_KEY", "").strip()
        if not e2b_key:
            raise SandboxUnavailableError("E2B API key missing. Host execution is strictly forbidden in production.")

        try:
            from e2b_code_interpreter import Sandbox
        except ImportError:
            raise SandboxUnavailableError("e2b_code_interpreter SDK missing. Cannot initialize cloud sandbox.")

        start_time = time.time()
        result = ExecutionResult(project_id=project_id)
        result.environment_used = {"runner": "e2b_firecracker", "project_type": plan.project_type}

        if not plan.executable or not files:
            result.overall_status = "SKIPPED"
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        sbx = None
        try:
            sbx = await asyncio.to_thread(Sandbox.create, api_key=e2b_key)
        except Exception as create_err:
            raise SandboxUnavailableError(f"E2B cloud sandbox creation failed: {create_err}")

        try:
            # Write files to E2B sandbox workspace
            for f in files:
                if isinstance(f, dict):
                    p = f.get("path", "").lstrip("/").lstrip("\\")
                    c = f.get("content", "")
                    if p and c:
                        await asyncio.to_thread(sbx.files.write, f"/home/user/{p}", c)

            cmds = plan.commands
            stages_to_run = [
                ("INSTALL", cmds.install, 120),
                ("BUILD", cmds.build, 60),
                ("TEST", cmds.test, 60),
                ("START", cmds.start, 20),
                ("HEALTH_CHECK", cmds.health_check, 15),
            ]

            overall_failed = False

            for stage_name, cmd_spec, timeout in stages_to_run:
                if overall_failed:
                    result.stages[stage_name] = StageResult(status="SKIPPED")
                    continue

                if stage_name == "HEALTH_CHECK" and isinstance(cmd_spec, HealthCheckSpec):
                    hc_start = time.time()
                    hc_spec: HealthCheckSpec = cmd_spec
                    cmd_str = f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{hc_spec.port}{hc_spec.path}"
                    
                    passed = False
                    last_code = ""
                    for attempt in range(8):
                        await asyncio.sleep(1.5)
                        try:
                            res = await asyncio.to_thread(sbx.commands.run, cmd_str, timeout=5)
                            last_code = res.stdout.strip()
                            if last_code in ("200", "201", "204", "301", "302", str(hc_spec.expected_status)):
                                passed = True
                                break
                        except Exception as e:
                            last_code = f"error: {e}"

                    duration = int((time.time() - hc_start) * 1000)
                    if passed:
                        result.stages[stage_name] = StageResult(
                            status="PASSED", exit_code=0, duration_ms=duration, stdout_snippet=f"HTTP probe -> {last_code}"
                        )
                    else:
                        overall_failed = True
                        result.failed_stage = stage_name
                        result.stages[stage_name] = StageResult(
                            status="FAILED", exit_code=1, duration_ms=duration, stderr_snippet=f"HTTP probe returned {last_code}"
                        )
                        result.error_signature = _generate_error_signature(stage_name, f"HTTP {last_code}")

                elif stage_name == "START" and cmd_spec:
                    st_start = time.time()
                    try:
                        res = await asyncio.to_thread(sbx.commands.run, cmd_spec, background=True)
                    except Exception:
                        res = await asyncio.to_thread(sbx.commands.run, f"nohup {cmd_spec} > /dev/null 2>&1 &")
                    await asyncio.sleep(2)
                    duration = int((time.time() - st_start) * 1000)
                    result.stages[stage_name] = StageResult(
                        status="PASSED", exit_code=0, duration_ms=duration, stdout_snippet=f"Started in E2B sandbox: {cmd_spec}"
                    )

                elif cmd_spec and isinstance(cmd_spec, str):
                    st_start = time.time()
                    try:
                        res = await asyncio.to_thread(sbx.commands.run, cmd_spec, timeout=timeout)
                        duration = int((time.time() - st_start) * 1000)
                        if getattr(res, "exit_code", 0) == 0:
                            result.stages[stage_name] = StageResult(
                                status="PASSED", exit_code=0, duration_ms=duration, stdout_snippet=_truncate_log(res.stdout)
                            )
                        else:
                            overall_failed = True
                            result.failed_stage = stage_name
                            result.stages[stage_name] = StageResult(
                                status="FAILED", exit_code=res.exit_code, duration_ms=duration,
                                stdout_snippet=_truncate_log(res.stdout), stderr_snippet=_truncate_log(res.stderr)
                            )
                            result.error_signature = _generate_error_signature(stage_name, res.stderr or res.stdout)
                    except Exception as cmd_err:
                        duration = int((time.time() - st_start) * 1000)
                        exit_code = getattr(cmd_err, "exit_code", 1) or 1
                        stdout_str = getattr(cmd_err, "stdout", "") or ""
                        stderr_str = getattr(cmd_err, "stderr", "") or str(cmd_err)
                        
                        overall_failed = True
                        result.failed_stage = stage_name
                        result.stages[stage_name] = StageResult(
                            status="FAILED", exit_code=exit_code, duration_ms=duration,
                            stdout_snippet=_truncate_log(stdout_str), stderr_snippet=_truncate_log(stderr_str)
                        )
                        result.error_signature = _generate_error_signature(stage_name, stderr_str or stdout_str)
                else:
                    result.stages[stage_name] = StageResult(status="SKIPPED")

            if not overall_failed:
                result.overall_status = "PASSED"

        except Exception as e:
            logger.error(f"E2B sandbox execution error: {e}")
            result.overall_status = "FAILED"
            result.failed_stage = result.failed_stage or "SETUP"
            result.error_signature = _generate_error_signature("SETUP", str(e))
        finally:
            if sbx:
                try:
                    await asyncio.to_thread(sbx.kill)
                except Exception:
                    pass

        result.duration_ms = int((time.time() - start_time) * 1000)
        return result


def get_sandbox_runner(env: Optional[str] = None, mode: Optional[str] = None) -> BaseSandboxRunner:
    """
    Factory function resolving sandbox runner based on environment and sandbox policy.
    Production defaults to e2b_required (fail-closed).
    """
    validate_sandbox_config(env=env, mode=mode)
    
    curr_env = (env if env is not None else get_environment()).strip().lower()
    curr_mode = (mode if mode is not None else get_sandbox_mode()).strip().lower()

    if curr_mode == "e2b_required":
        e2b_key = os.getenv("E2B_API_KEY", "").strip()
        if not e2b_key:
            raise SandboxUnavailableError("E2B API key missing. Host execution is strictly forbidden in production.")
        return E2BSandboxRunner()
    elif curr_mode == "local_dev":
        if curr_env == "production":
            raise ValueError("Security Violation: LocalSubprocessSandboxRunner is strictly forbidden in production.")
        return LocalSubprocessSandboxRunner()
    else:
        raise ValueError(f"Invalid SANDBOX_MODE: {curr_mode}")


from app.services.resource_budget import resource_budget, ResourceBudgetExceededError

async def run_sandbox_execution(
    project_id: str,
    files: List[dict],
    plan: ExecutionPlan,
    custom_runner: Optional[BaseSandboxRunner] = None
) -> ExecutionResult:
    """
    Main sandbox entrypoint. Resolves sandbox runner per security policy and returns
    structured ExecutionResult. Fails closed with SANDBOX_INIT stage if cloud sandbox unavailable
    or resource budget is exceeded.
    """
    start_time = time.time()
    try:
        resource_budget.check_e2b_budget(project_id)
        runner = custom_runner or get_sandbox_runner()
        res = await runner.execute(project_id, files, plan)
        resource_budget.record_e2b_execution(project_id)
        return res
    except (SandboxUnavailableError, ResourceBudgetExceededError) as e:
        logger.error(f"Sandbox execution rejected for project {project_id}: {e}")
        duration = int((time.time() - start_time) * 1000)
        res = ExecutionResult(
            project_id=project_id,
            overall_status="FAILED",
            failed_stage="SANDBOX_INIT",
            duration_ms=duration
        )
        res.stages["SANDBOX_INIT"] = StageResult(
            status="FAILED",
            exit_code=1,
            duration_ms=duration,
            stderr_snippet=f"Sandbox initialization failed: {e}"
        )
        res.error_signature = _generate_error_signature("SANDBOX_INIT", str(e))
        return res
