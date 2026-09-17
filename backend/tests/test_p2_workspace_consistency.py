import pytest
import asyncio
from unittest.mock import patch, MagicMock

from app.models.execution_schema import FinalValidationResult
from app.models.schemas import AgentRole, ProjectStatus
from app.core.database import (
    get_db,
    create_project,
    get_project,
    save_agent_output,
    now_iso,
)
from app.core.artifact_store import get_artifact_store
from app.services.orchestrator import Orchestrator


async def helper_create_project(project_id: str, user_id: str, problem_statement: str):
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
async def test_new_engineer_execution_reconstructs_workspace_from_canonical_files():
    """P2 Test: New Engineer execution starts from canonical files A, clearing stale workspace files B."""
    orchestrator = Orchestrator()
    project_id = "test_p2_workspace_01"
    await helper_create_project(project_id, "user1", "Test Workspace Consistency")

    store = get_artifact_store()
    
    # 1. Simulate stale workspace left by abandoned execution containing files B
    await store.write_file(project_id, "stale_b.py", "print('stale file B')")
    await store.write_file(project_id, "shared.py", "stale_version_b")
    
    stale_files = await store.list_files(project_id)
    assert "stale_b.py" in stale_files
    assert "shared.py" in stale_files

    # 2. Canonical Engineer files A
    canonical_files_a = [
        {"path": "main.py", "content": "print('canonical file A')"},
        {"path": "shared.py", "content": "canonical_version_a"}
    ]

    val_res = FinalValidationResult(
        attempts_used=1,
        final_status="VALIDATED",
        final_files=canonical_files_a
    )

    # 3. Trigger new Engineer execution
    with patch("app.services.orchestrator.run_agent") as mock_agent, \
         patch("app.services.orchestrator.RepairLoopService.run_repair_loop", return_value=val_res):
        
        mock_agent.return_value = {
            "id": "out_eng_p2",
            "content": {"files": canonical_files_a}
        }

        await orchestrator._start_next_agent(project_id, AgentRole.ENGINEER)
        task = orchestrator._running_tasks.get(project_id)
        if task:
            await task

    # 4. Verify workspace starts from A, not B
    current_files = await store.list_files(project_id)
    assert "main.py" in current_files
    assert "shared.py" in current_files
    assert "stale_b.py" not in current_files, "Stale file B must be removed from workspace"

    shared_content = (await store.read_file(project_id, "shared.py")).decode("utf-8")
    assert shared_content == "canonical_version_a", "Workspace file must contain canonical A content"
