import pytest
import json
import os
import tempfile
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.execution_schema import (
    FinalValidationResult,
    ExecutionPlan,
    DefinitionOfDone,
    DoDItem,
)
from app.models.schemas import AgentRole, ProjectStatus
from app.core.database import (
    get_db,
    create_project,
    get_project,
    save_agent_output,
    get_latest_output,
    get_memory,
    set_memory,
    update_agent_output_content,
    update_project_status,
    now_iso,
)
from app.services.repair_loop import RepairLoopService
from app.services.orchestrator import Orchestrator
from app.services.file_generator import (
    generate_project_files,
    get_generated_files_list,
    get_generated_file_contents,
)


async def helper_create_project(project_id: str, user_id: str, problem_statement: str):
    """Helper to insert project with explicit project_id for testing."""
    db = await get_db()
    try:
        ts = now_iso()
        await db.execute(
            "INSERT INTO projects (id, problem_statement, status, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, problem_statement, "created", user_id, ts, ts),
        )
        await db.commit()
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_validated_result_populates_final_files():
    """Test 1: VALIDATED result populates final_files with repaired files."""
    service = RepairLoopService()
    project_id = "test_val_files_01"
    files = [{"path": "main.py", "content": "print('original')"}]
    plan = ExecutionPlan(project_type="python")
    plan.executable = True
    from app.models.execution_schema import HealthCheckSpec
    plan.commands.health_check = HealthCheckSpec(port=8000, path="/", expected_status=200)
    dod = DefinitionOfDone(items=[DoDItem(id="1", description="pass")])

    ba_output = {"functional_requirements": ["Users can create tasks", "Users can list tasks"]}
    architect_output = {"api_structure": [{"method": "GET", "path": "/api/tasks", "purpose": "List tasks"}]}

    mock_exec_obj = MagicMock()
    mock_exec_obj.project_id = project_id
    mock_exec_obj.overall_status = "PASS"
    mock_exec_obj.failed_stage = None
    mock_exec_obj.model_dump = lambda: {"overall_status": "PASS"}
    mock_exec_obj.independent_qa_result = {
        "status": "PASS", "assertions_total": 1, "assertions_passed": 1,
        "assertions_failed": 0, "results": [], "reason": "OK"
    }

    mock_qa_obj = MagicMock()
    mock_qa_obj.status = "PASS"
    mock_qa_obj.model_dump = lambda: {"status": "PASS"}

    with patch("app.services.repair_loop.run_sandbox_execution", return_value=mock_exec_obj), \
         patch("app.services.repair_loop.evaluate_qa_results", return_value=mock_qa_obj):

        res = await service.run_repair_loop(
            project_id=project_id,
            files=files,
            plan=plan,
            dod=dod,
            ba_output=ba_output,
            architect_output=architect_output,
        )

        assert res.final_status == "VALIDATED"
        assert res.final_files == files


@pytest.mark.asyncio
async def test_persisted_engineer_output_contains_repaired_files():
    """Test 2: Persisted engineer output in DB contains repaired files, not original files."""
    project_id = "test_persist_rep_02"
    await helper_create_project(project_id, "user1", "Test Repaired Persistence")
    
    orig_content = {"files": [{"path": "calc.py", "content": "def add(a, b): return 0"}]}
    out = await save_agent_output(project_id, AgentRole.ENGINEER.value, orig_content)
    
    repaired_files = [{"path": "calc.py", "content": "def add(a, b): return a + b"}]
    orig_content["files"] = repaired_files
    
    await update_agent_output_content(out["id"], project_id, orig_content)
    
    latest = await get_latest_output(project_id, AgentRole.ENGINEER.value)
    assert latest["content"]["files"] == repaired_files
    assert latest["content"]["files"] != [{"path": "calc.py", "content": "def add(a, b): return 0"}]


@pytest.mark.asyncio
async def test_zip_generation_uses_repaired_files():
    """Test 3: ZIP generation uses repaired/validated files."""
    project_id = "test_zip_rep_03"
    await helper_create_project(project_id, "user1", "Test Zip Repaired")
    
    repaired_files = [{"path": "app.py", "content": "print('hello validated world')"}]
    content = {"files": repaired_files}
    
    await generate_project_files(project_id, content)
    files_list = await get_generated_files_list(project_id)
    assert "app.py" in files_list
    
    file_contents = await get_generated_file_contents(project_id)
    app_file = next(f for f in file_contents if f["path"] == "app.py")
    assert app_file["content"] == "print('hello validated world')"


@pytest.mark.asyncio
async def test_validation_failed_does_not_transition_to_engineer_review():
    """Test 4: VALIDATION_FAILED does not transition project to engineer_review."""
    orchestrator = Orchestrator()
    project_id = "test_failed_no_review_04"
    await helper_create_project(project_id, "user1", "Test Fail Gate")
    
    failed_res = FinalValidationResult(
        attempts_used=3,
        final_status="VALIDATION_FAILED",
        reason="Max repair attempts exhausted."
    )
    
    with patch("app.services.orchestrator.run_agent") as mock_agent, \
         patch("app.services.orchestrator.RepairLoopService.run_repair_loop", return_value=failed_res):
        
        mock_agent.return_value = {
            "id": "out_eng_04",
            "content": {"files": [{"path": "broken.py", "content": "error"}]}
        }
        
        await orchestrator._start_next_agent(project_id, AgentRole.ENGINEER)
        task = orchestrator._running_tasks.get(project_id)
        if task:
            await task
        
        proj = await get_project(project_id)
        assert proj["status"] == ProjectStatus.FAILED.value
        assert proj["status"] != ProjectStatus.ENGINEER_REVIEW.value


@pytest.mark.asyncio
async def test_validation_failed_cannot_trigger_ppt():
    """Test 5 & 6: VALIDATION_FAILED cannot trigger PPT or reach COMPLETED."""
    orchestrator = Orchestrator()
    project_id = "test_no_ppt_05"
    await helper_create_project(project_id, "user1", "Test No PPT")
    
    val_res = FinalValidationResult(
        attempts_used=3,
        final_status="VALIDATION_FAILED",
        reason="Execution failed"
    )
    await set_memory(project_id, "final_validation_result", val_res.model_dump_json(), "test")
    out = await save_agent_output(project_id, AgentRole.ENGINEER.value, {"files": []})
    await update_project_status(project_id, ProjectStatus.ENGINEER_REVIEW.value)
    
    with patch.object(orchestrator, "_start_next_agent") as mock_next:
        await orchestrator.handle_approval(project_id, out["id"], approved=True)
        
        mock_next.assert_not_called()
        proj = await get_project(project_id)
        assert proj["status"] == ProjectStatus.FAILED.value
        assert proj["status"] != ProjectStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_repair_failed_cannot_reach_completed():
    """Test 7: REPAIR_FAILED cannot reach COMPLETED."""
    orchestrator = Orchestrator()
    project_id = "test_repair_fail_07"
    await helper_create_project(project_id, "user1", "Test Repair Fail")
    
    val_res = FinalValidationResult(
        attempts_used=2,
        final_status="REPAIR_FAILED",
        reason="Budget exceeded"
    )
    await set_memory(project_id, "final_validation_result", val_res.model_dump_json(), "test")
    out = await save_agent_output(project_id, AgentRole.ENGINEER.value, {"files": []})
    await update_project_status(project_id, ProjectStatus.ENGINEER_REVIEW.value)
    
    with patch.object(orchestrator, "_start_next_agent") as mock_next:
        await orchestrator.handle_approval(project_id, out["id"], approved=True)
        
        mock_next.assert_not_called()
        proj = await get_project(project_id)
        assert proj["status"] == ProjectStatus.FAILED.value


@pytest.mark.asyncio
async def test_approval_defense_rejects_non_validated_result():
    """Test 8: Approval defense rejects non-VALIDATED final result."""
    orchestrator = Orchestrator()
    project_id = "test_defense_08"
    await helper_create_project(project_id, "user1", "Test Defense")
    
    out = await save_agent_output(project_id, AgentRole.ENGINEER.value, {"files": []})
    await update_project_status(project_id, ProjectStatus.ENGINEER_REVIEW.value)
    
    with patch.object(orchestrator, "_start_next_agent") as mock_next:
        await orchestrator.handle_approval(project_id, out["id"], approved=True)
        
        mock_next.assert_not_called()
        proj = await get_project(project_id)
        assert proj["status"] == ProjectStatus.FAILED.value


@pytest.mark.asyncio
async def test_validated_project_follows_normal_approval_flow():
    """Test 9: VALIDATED project still follows normal approval flow."""
    orchestrator = Orchestrator()
    project_id = "test_normal_flow_09"
    await helper_create_project(project_id, "user1", "Test Normal Flow")
    
    val_res = FinalValidationResult(
        attempts_used=1,
        final_status="VALIDATED",
        final_files=[{"path": "index.js", "content": "console.log('ok')"}]
    )
    await set_memory(project_id, "final_validation_result", val_res.model_dump_json(), "test")
    out = await save_agent_output(project_id, AgentRole.ENGINEER.value, {"files": val_res.final_files})
    await update_project_status(project_id, ProjectStatus.ENGINEER_REVIEW.value)
    
    with patch.object(orchestrator, "_start_next_agent") as mock_next, \
         patch("app.services.orchestrator.generate_project_files", return_value=None):
        
        await orchestrator.handle_approval(project_id, out["id"], approved=True)
        
        mock_next.assert_called_once_with(project_id, AgentRole.PPT, execution_id=None)
