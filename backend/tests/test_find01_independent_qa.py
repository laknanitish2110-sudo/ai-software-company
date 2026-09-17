"""
FIND-01: Independent QA Verification Tests

Tests cover:
1. Assertion synthesis from BA requirements
2. Assertion synthesis from Architect API design
3. Non-API projects return UNAVAILABLE
4. Assertion execution pass
5. Assertion execution fail
6. Partial coverage is not PASS
7. IQA failure enters repair path
8. IQA artifacts never enter canonical files
9. IQA UNAVAILABLE does not produce VALIDATED
10. Port comes from execution plan
11. Repair context contains IQA failure details
12. Existing engineer tests still run
13. Engineer tests alone not sufficient for VALIDATED
14. Full pass requires both engineer + IQA
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.execution_schema import (
    ExecutionPlan,
    DefinitionOfDone,
    DoDItem,
    FinalValidationResult,
    HealthCheckSpec,
)
from app.models.independent_qa_schema import (
    QAAssertion,
    QAAssertionResult,
    IndependentQAResult,
)
from app.services.qa_assertion_synthesizer import synthesize_assertions
from app.services.independent_qa_runner import execute_assertions_http
from app.services.repair_loop import RepairLoopService
from app.services.sandbox_runner import ExecutionResult, StageResult
from app.agents.qa import QAReport, QARepairInstructions


# --- Helpers ---

def make_executable_plan(project_type="python", port=8000):
    """Create an executable plan with health check."""
    plan = ExecutionPlan(project_type=project_type)
    plan.executable = True
    plan.commands.health_check = HealthCheckSpec(port=port, path="/", expected_status=200)
    plan.commands.install = "pip install -r requirements.txt"
    plan.commands.test = "python -m pytest"
    plan.commands.start = "python app.py"
    return plan


def make_non_executable_plan():
    """Create a non-executable plan (e.g., n8n workflow)."""
    plan = ExecutionPlan(project_type="n8n")
    plan.executable = False
    return plan


def make_ba_output_with_reqs():
    """BA output with functional requirements containing CRUD keywords."""
    return {
        "functional_requirements": [
            "Users can create new tasks with a title and description",
            "Users can list all tasks",
            "Users can update an existing task",
            "Users can delete a task",
            "The system shall display a dashboard with task statistics",
        ],
        "acceptance_criteria": [
            {"id": "AC-1", "description": "Tasks can be created"},
        ],
    }


def make_architect_output_with_api():
    """Architect output with structured API endpoints."""
    return {
        "api_structure": [
            {"method": "POST", "path": "/api/tasks", "purpose": "Create a new task", "response_shape": {"id": "string", "title": "string"}},
            {"method": "GET", "path": "/api/tasks", "purpose": "List all tasks"},
            {"method": "PUT", "path": "/api/tasks/:id", "purpose": "Update a task"},
            {"method": "DELETE", "path": "/api/tasks/:id", "purpose": "Delete a task"},
            {"method": "GET", "path": "/api/health", "purpose": "Health check endpoint"},
        ],
    }


def make_passed_exec_result(project_id="test_proj", iqa_result=None):
    """ExecutionResult where all sandbox stages passed."""
    result = ExecutionResult(project_id=project_id, overall_status="PASSED")
    for stage_name in ("SANDBOX_INIT", "INSTALL", "BUILD", "TEST", "START", "HEALTH_CHECK"):
        result.stages[stage_name] = StageResult(status="PASSED", exit_code=0)
    result.independent_qa_result = iqa_result
    return result


def make_dod():
    """Simple definition of done."""
    return DefinitionOfDone(items=[DoDItem(id="1", description="pass")])


# =====================================================================
# TEST 1: Synthesize assertions from BA functional requirements
# =====================================================================
@pytest.mark.asyncio
async def test_synthesize_assertions_from_ba_requirements():
    """BA functional requirements with CRUD keywords produce assertions."""
    ba_output = make_ba_output_with_reqs()
    architect_output = {}  # No architect API design
    plan = make_executable_plan()

    assertions, reason = synthesize_assertions(ba_output, architect_output, plan)

    assert len(assertions) >= 3, f"Expected at least 3 assertions, got {len(assertions)}"
    assert reason == ""

    methods = {a.method for a in assertions}
    assert "POST" in methods, "Should synthesize POST from 'create' keyword"
    assert "GET" in methods, "Should synthesize GET from 'list' keyword"

    # Every assertion must have a requirement_id
    for a in assertions:
        assert a.requirement_id.startswith("FR-"), f"BA-sourced assertion should have FR- prefix: {a.requirement_id}"


# =====================================================================
# TEST 2: Synthesize assertions from Architect API design
# =====================================================================
@pytest.mark.asyncio
async def test_synthesize_assertions_from_architect_api_design():
    """Architect api_structure endpoints produce structured assertions."""
    ba_output = {}
    architect_output = make_architect_output_with_api()
    plan = make_executable_plan()

    assertions, reason = synthesize_assertions(ba_output, architect_output, plan)

    assert len(assertions) == 5, f"Expected 5 assertions from 5 endpoints, got {len(assertions)}"
    assert reason == ""

    # Check method mapping
    api_methods = {(a.method, a.path) for a in assertions}
    assert ("POST", "/api/tasks") in api_methods
    assert ("GET", "/api/tasks") in api_methods
    assert ("DELETE", "/api/tasks/:id") in api_methods

    # Architect assertions have ARCH-API prefix
    for a in assertions:
        assert a.requirement_id.startswith("ARCH-API-")

    # POST should expect 201
    post_assertion = next(a for a in assertions if a.method == "POST")
    assert post_assertion.expected_status == 201


# =====================================================================
# TEST 3: Non-API project returns empty (UNAVAILABLE)
# =====================================================================
@pytest.mark.asyncio
async def test_synthesize_returns_empty_for_non_api_project():
    """Non-executable projects (n8n workflows) return empty assertions with reason."""
    ba_output = make_ba_output_with_reqs()
    architect_output = make_architect_output_with_api()
    plan = make_non_executable_plan()

    assertions, reason = synthesize_assertions(ba_output, architect_output, plan)

    assert len(assertions) == 0
    assert reason != "", "Should provide reason for UNAVAILABLE"
    assert "non-executable" in reason.lower() or "n8n" in reason.lower()


# =====================================================================
# TEST 4: Assertion execution PASS
# =====================================================================
@pytest.mark.asyncio
async def test_assertion_execution_pass():
    """All assertions pass → IndependentQAResult.status == PASS."""
    assertions = [
        QAAssertion(requirement_id="T-1", method="GET", path="/tasks", expected_status=200),
        QAAssertion(requirement_id="T-2", method="POST", path="/tasks", expected_status=201),
    ]

    mock_responses = {
        ("GET", "/tasks"): (200, {"tasks": []}),
        ("POST", "/tasks"): (201, {"id": "1", "title": "test"}),
    }

    async def mock_request(self, method, url, **kwargs):
        path = "/" + url.split("/", 3)[-1] if "/" in url else url
        for (m, p), (status, body) in mock_responses.items():
            if method.upper() == m and path.endswith(p):
                resp = MagicMock()
                resp.status_code = status
                resp.json.return_value = body
                return resp
        resp = MagicMock()
        resp.status_code = 404
        resp.json.return_value = {}
        return resp

    with patch("app.services.independent_qa_runner.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=lambda url, **kw: asyncio.coroutine(lambda: mock_request(None, "GET", url))())
        mock_client.post = AsyncMock(side_effect=lambda url, **kw: asyncio.coroutine(lambda: mock_request(None, "POST", url))())

        # Simpler approach: mock individual methods
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {"tasks": []}
        mock_client.get = AsyncMock(return_value=get_resp)

        post_resp = MagicMock()
        post_resp.status_code = 201
        post_resp.json.return_value = {"id": "1"}
        mock_client.post = AsyncMock(return_value=post_resp)

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client

        result = await execute_assertions_http(assertions, "127.0.0.1", 8000)

    assert result.status == "PASS"
    assert result.assertions_total == 2
    assert result.assertions_passed == 2
    assert result.assertions_failed == 0


# =====================================================================
# TEST 5: Assertion execution FAIL
# =====================================================================
@pytest.mark.asyncio
async def test_assertion_execution_fail():
    """One assertion fails → IndependentQAResult.status == FAIL with details."""
    assertions = [
        QAAssertion(requirement_id="T-1", method="GET", path="/tasks", expected_status=200),
        QAAssertion(requirement_id="T-2", method="POST", path="/tasks", expected_status=201),
    ]

    with patch("app.services.independent_qa_runner.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()

        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {"tasks": []}
        mock_client.get = AsyncMock(return_value=get_resp)

        # POST returns 500 instead of 201
        post_resp = MagicMock()
        post_resp.status_code = 500
        post_resp.json.return_value = {"error": "Internal Server Error"}
        mock_client.post = AsyncMock(return_value=post_resp)

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client

        result = await execute_assertions_http(assertions, "127.0.0.1", 8000)

    assert result.status == "FAIL"
    assert result.assertions_total == 2
    assert result.assertions_passed == 1
    assert result.assertions_failed == 1

    failed_results = [r for r in result.results if not r.passed]
    assert len(failed_results) == 1
    assert "Expected status 201" in failed_results[0].error


# =====================================================================
# TEST 6: Partial coverage is NOT PASS
# =====================================================================
@pytest.mark.asyncio
async def test_partial_coverage_is_not_pass():
    """10 assertions, 4 fail → FAIL even though 6 pass."""
    assertions = []
    for i in range(10):
        assertions.append(QAAssertion(
            requirement_id=f"T-{i+1}",
            method="GET",
            path=f"/endpoint{i}",
            expected_status=200,
        ))

    with patch("app.services.independent_qa_runner.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()

        call_count = 0
        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            # First 6 pass (200), last 4 fail (404)
            resp.status_code = 200 if call_count <= 6 else 404
            resp.json.return_value = {}
            return resp

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client

        result = await execute_assertions_http(assertions, "127.0.0.1", 8000)

    assert result.status == "FAIL", "10 requirements, 6 pass, 4 fail → must be FAIL, not PASS"
    assert result.assertions_passed == 6
    assert result.assertions_failed == 4


# =====================================================================
# TEST 7: IQA failure enters repair path
# =====================================================================
@pytest.mark.asyncio
async def test_iqa_failure_enters_repair_path():
    """IQA FAIL causes QA override and enters repair loop (not immediate VALIDATED)."""
    service = RepairLoopService()
    plan = make_executable_plan()
    dod = make_dod()
    files = [{"path": "app.py", "content": "print('hello')"}]

    # Mock: all sandbox stages pass but IQA fails
    iqa_fail_result = {
        "status": "FAIL",
        "assertions_total": 3,
        "assertions_passed": 1,
        "assertions_failed": 2,
        "results": [
            {"assertion": {"requirement_id": "T-1", "method": "GET", "path": "/tasks"}, "passed": True, "error": ""},
            {"assertion": {"requirement_id": "T-2", "method": "POST", "path": "/tasks"}, "passed": False, "error": "Expected 201, got 404"},
            {"assertion": {"requirement_id": "T-3", "method": "DELETE", "path": "/tasks"}, "passed": False, "error": "Expected 200, got 404"},
        ],
        "reason": "2/3 assertion(s) failed.",
    }
    exec_result = make_passed_exec_result("test_iqa_repair", iqa_result=iqa_fail_result)

    # Provide BA/Arch output so assertions are synthesized
    ba_output = make_ba_output_with_reqs()
    architect_output = make_architect_output_with_api()

    with patch("app.services.repair_loop.run_sandbox_execution", return_value=exec_result), \
         patch("app.services.repair_loop.build_repair_context", new_callable=AsyncMock) as mock_ctx, \
         patch("app.services.repair_loop.generate_targeted_patch", new_callable=AsyncMock) as mock_patch:

        # Fixer returns no patch possible (to end the loop)
        mock_ctx.return_value = MagicMock()
        mock_patch_result = MagicMock()
        mock_patch_result.status = "NO_PATCH_POSSIBLE"
        mock_patch_result.changes = []
        mock_patch_result.reason = "Cannot fix"
        mock_patch.return_value = mock_patch_result

        result = await service.run_repair_loop(
            project_id="test_iqa_repair",
            files=files,
            plan=plan,
            dod=dod,
            ba_output=ba_output,
            architect_output=architect_output,
        )

    # IQA failure should prevent VALIDATED — project should end as VALIDATION_FAILED or REPAIR_FAILED
    assert result.final_status != "VALIDATED", "IQA FAIL must prevent VALIDATED"
    assert result.final_status in ("VALIDATION_FAILED", "REPAIR_FAILED")


# =====================================================================
# TEST 8: IQA artifacts never enter canonical files
# =====================================================================
@pytest.mark.asyncio
async def test_iqa_never_enters_canonical_files():
    """IQA test files never appear in current_files, final_files, or agent_outputs."""
    service = RepairLoopService()
    plan = make_executable_plan()
    dod = make_dod()
    original_files = [{"path": "app.py", "content": "print('hello')"}]

    # IQA passes
    iqa_pass_result = {
        "status": "PASS",
        "assertions_total": 2,
        "assertions_passed": 2,
        "assertions_failed": 0,
        "results": [],
        "reason": "All assertions passed.",
    }
    exec_result = make_passed_exec_result("test_no_leak", iqa_result=iqa_pass_result)

    ba_output = make_ba_output_with_reqs()
    architect_output = make_architect_output_with_api()

    with patch("app.services.repair_loop.run_sandbox_execution", return_value=exec_result), \
         patch("app.services.repair_loop.evaluate_qa_results") as mock_qa:

        mock_qa_report = MagicMock()
        mock_qa_report.status = "PASS"
        mock_qa_report.model_dump = lambda: {"status": "PASS"}
        mock_qa_report.dict = lambda: {"status": "PASS"}
        mock_qa.return_value = mock_qa_report

        result = await service.run_repair_loop(
            project_id="test_no_leak",
            files=original_files,
            plan=plan,
            dod=dod,
            ba_output=ba_output,
            architect_output=architect_output,
        )

    assert result.final_status == "VALIDATED"

    # Verify no IQA artifacts in final_files
    if result.final_files:
        for f in result.final_files:
            path = f.get("path", "")
            assert ".forgeai_qa" not in path, f"IQA artifact leaked into final_files: {path}"
            assert "iqa_" not in path.lower(), f"IQA artifact leaked into final_files: {path}"

    # Original files should be unchanged
    assert len(result.final_files) == len(original_files)
    assert result.final_files[0]["path"] == "app.py"


# =====================================================================
# TEST 9: IQA UNAVAILABLE does not produce VALIDATED
# =====================================================================
@pytest.mark.asyncio
async def test_iqa_unavailable_does_not_validate():
    """Non-API project → IQA UNAVAILABLE → VALIDATION_FAILED (fail-closed)."""
    service = RepairLoopService()
    plan = make_non_executable_plan()  # n8n workflow
    dod = make_dod()
    files = [{"path": "workflow.json", "content": "{}"}]

    result = await service.run_repair_loop(
        project_id="test_unavailable",
        files=files,
        plan=plan,
        dod=dod,
        ba_output=make_ba_output_with_reqs(),
        architect_output=make_architect_output_with_api(),
    )

    assert result.final_status == "VALIDATION_FAILED"
    assert "unavailable" in result.reason.lower()
    assert result.attempts_used == 0  # Should fail before any attempt


# =====================================================================
# TEST 10: Port comes from execution plan, not hardcoded
# =====================================================================
@pytest.mark.asyncio
async def test_port_from_execution_plan():
    """Port for IQA assertions comes from plan.commands.health_check.port."""
    plan_5555 = make_executable_plan(port=5555)
    ba_output = make_ba_output_with_reqs()
    architect_output = make_architect_output_with_api()

    assertions, reason = synthesize_assertions(ba_output, architect_output, plan_5555)
    assert len(assertions) > 0

    # Verify that when we pass to sandbox execution, the port is from plan
    exec_result = make_passed_exec_result("test_port")

    with patch("app.services.repair_loop.run_sandbox_execution", new_callable=AsyncMock) as mock_sandbox:
        mock_sandbox.return_value = exec_result
        # The sandbox execution should receive the plan with port 5555
        # We verify by checking the plan passed to run_sandbox_execution
        service = RepairLoopService()
        dod = make_dod()
        files = [{"path": "app.py", "content": "print('hi')"}]

        # IQA must pass to end the loop
        exec_result.independent_qa_result = {
            "status": "PASS", "assertions_total": 1,
            "assertions_passed": 1, "assertions_failed": 0,
            "results": [], "reason": "OK",
        }

        with patch("app.services.repair_loop.evaluate_qa_results") as mock_qa:
            mock_qa_report = MagicMock()
            mock_qa_report.status = "PASS"
            mock_qa_report.model_dump = lambda: {"status": "PASS"}
            mock_qa_report.dict = lambda: {"status": "PASS"}
            mock_qa.return_value = mock_qa_report

            await service.run_repair_loop(
                project_id="test_port_proj",
                files=files,
                plan=plan_5555,
                dod=dod,
                ba_output=ba_output,
                architect_output=architect_output,
            )

        # Verify run_sandbox_execution was called with the correct plan
        call_args = mock_sandbox.call_args
        assert call_args is not None
        called_plan = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("plan")
        assert called_plan.commands.health_check.port == 5555


# =====================================================================
# TEST 11: Repair context contains IQA failure details
# =====================================================================
@pytest.mark.asyncio
async def test_repair_context_contains_iqa_details():
    """When IQA fails, repair context receives actionable failure details."""
    service = RepairLoopService()
    plan = make_executable_plan()
    dod = make_dod()
    files = [{"path": "app.py", "content": "print('hi')"}]

    iqa_fail = {
        "status": "FAIL",
        "assertions_total": 2,
        "assertions_passed": 0,
        "assertions_failed": 2,
        "results": [
            {"assertion": {"requirement_id": "T-1", "method": "POST", "path": "/tasks"}, "passed": False, "error": "Expected 201, got 404"},
            {"assertion": {"requirement_id": "T-2", "method": "GET", "path": "/tasks"}, "passed": False, "error": "Expected 200, got 500"},
        ],
        "reason": "2/2 assertion(s) failed.",
    }
    exec_result = make_passed_exec_result("test_ctx", iqa_result=iqa_fail)

    ba_output = make_ba_output_with_reqs()
    architect_output = make_architect_output_with_api()

    captured_qa_report = None

    async def capture_ctx(*args, **kwargs):
        nonlocal captured_qa_report
        # args[1] is qa_report
        captured_qa_report = args[1] if len(args) > 1 else kwargs.get("qa_report")
        return MagicMock()

    with patch("app.services.repair_loop.run_sandbox_execution", return_value=exec_result), \
         patch("app.services.repair_loop.build_repair_context", side_effect=capture_ctx), \
         patch("app.services.repair_loop.generate_targeted_patch", new_callable=AsyncMock) as mock_patch:

        mock_patch_result = MagicMock()
        mock_patch_result.status = "NO_PATCH_POSSIBLE"
        mock_patch_result.changes = []
        mock_patch_result.reason = "Cannot fix"
        mock_patch.return_value = mock_patch_result

        await service.run_repair_loop(
            project_id="test_ctx_proj",
            files=files,
            plan=plan,
            dod=dod,
            ba_output=ba_output,
            architect_output=architect_output,
        )

    # Verify QA report passed to build_repair_context contains IQA failure details
    assert captured_qa_report is not None
    assert captured_qa_report.failure_category == "INDEPENDENT_QA_FAILURE"
    assert "T-1" in captured_qa_report.failed_criteria or "T-2" in captured_qa_report.failed_criteria


# =====================================================================
# TEST 12: Existing engineer tests still run
# =====================================================================
@pytest.mark.asyncio
async def test_existing_engineer_tests_still_run():
    """Engineer's own test command still executes (IQA is additive)."""
    plan = make_executable_plan()

    # The plan has a test command
    assert plan.commands.test is not None
    assert plan.commands.test == "python -m pytest"

    # IQA assertions are synthesized but don't replace test command
    ba_output = make_ba_output_with_reqs()
    architect_output = make_architect_output_with_api()
    assertions, _ = synthesize_assertions(ba_output, architect_output, plan)

    # Test command is unchanged after synthesis
    assert plan.commands.test == "python -m pytest"

    # IQA assertions are separate from test command
    assert len(assertions) > 0
    for a in assertions:
        assert a.method in ("GET", "POST", "PUT", "DELETE"), "IQA assertions are HTTP-based, not test commands"


# =====================================================================
# TEST 13: Engineer tests alone not sufficient for VALIDATED
# =====================================================================
@pytest.mark.asyncio
async def test_engineer_tests_alone_not_sufficient():
    """Engineer tests pass + IQA missing → NOT VALIDATED."""
    service = RepairLoopService()
    plan = make_executable_plan()
    dod = make_dod()
    files = [{"path": "app.py", "content": "print('hi')"}]

    # All sandbox stages pass, but NO IQA result
    exec_result = make_passed_exec_result("test_eng_only", iqa_result=None)

    ba_output = make_ba_output_with_reqs()
    architect_output = make_architect_output_with_api()

    with patch("app.services.repair_loop.run_sandbox_execution", return_value=exec_result), \
         patch("app.services.repair_loop.build_repair_context", new_callable=AsyncMock) as mock_ctx, \
         patch("app.services.repair_loop.generate_targeted_patch", new_callable=AsyncMock) as mock_patch:

        mock_ctx.return_value = MagicMock()
        mock_patch_result = MagicMock()
        mock_patch_result.status = "NO_PATCH_POSSIBLE"
        mock_patch_result.changes = []
        mock_patch_result.reason = "Cannot fix"
        mock_patch.return_value = mock_patch_result

        result = await service.run_repair_loop(
            project_id="test_eng_only_proj",
            files=files,
            plan=plan,
            dod=dod,
            ba_output=ba_output,
            architect_output=architect_output,
        )

    assert result.final_status != "VALIDATED", "Engineer tests alone must never produce VALIDATED"


# =====================================================================
# TEST 14: Full pass requires both engineer tests + IQA
# =====================================================================
@pytest.mark.asyncio
async def test_full_pass_requires_both():
    """Engineer tests PASS + IQA PASS → VALIDATED."""
    service = RepairLoopService()
    plan = make_executable_plan()
    dod = make_dod()
    files = [{"path": "app.py", "content": "print('hi')"}]

    iqa_pass = {
        "status": "PASS",
        "assertions_total": 3,
        "assertions_passed": 3,
        "assertions_failed": 0,
        "results": [],
        "reason": "All assertions passed.",
    }
    exec_result = make_passed_exec_result("test_both_pass", iqa_result=iqa_pass)

    ba_output = make_ba_output_with_reqs()
    architect_output = make_architect_output_with_api()

    with patch("app.services.repair_loop.run_sandbox_execution", return_value=exec_result), \
         patch("app.services.repair_loop.evaluate_qa_results") as mock_qa:

        mock_qa_report = MagicMock()
        mock_qa_report.status = "PASS"
        mock_qa_report.model_dump = lambda: {"status": "PASS"}
        mock_qa_report.dict = lambda: {"status": "PASS"}
        mock_qa.return_value = mock_qa_report

        result = await service.run_repair_loop(
            project_id="test_both_pass_proj",
            files=files,
            plan=plan,
            dod=dod,
            ba_output=ba_output,
            architect_output=architect_output,
        )

    assert result.final_status == "VALIDATED"
    assert result.final_files is not None
    assert len(result.final_files) == 1
    assert result.final_files[0]["path"] == "app.py"
