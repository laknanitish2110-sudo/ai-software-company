import os
import time
import logging
from typing import List, Dict, Any, Tuple, Optional

from app.models.execution_schema import (
    PatchResult,
    FilePatch,
    PatchApplyResult,
    ProjectSnapshot
)
from app.core.artifact_store import get_artifact_store
from app.agents.fixer import compute_patch_hash, MAX_PATCH_FILES, MAX_FILE_PATCH_CHARS, ALLOWED_ACTIONS

logger = logging.getLogger(__name__)


class PatchApplier:
    """
    Dedicated service for safely applying LLM-generated targeted patches.
    Enforces atomic file writes, filesystem boundary security, and snapshot rollback capabilities.
    """
    async def create_snapshot(self, project_id: str, memory_files: List[dict]) -> ProjectSnapshot:
        """Captures a pre-patch snapshot of project files for rollback."""
        files_backup = {}
        store = get_artifact_store()
        
        # Capture memory files (and their disk state)
        if isinstance(memory_files, list):
            for f in memory_files:
                if isinstance(f, dict) and f.get("path"):
                    norm = f["path"].lstrip("/").lstrip("\\").replace("\\", "/")
                    if await store.file_exists(project_id, norm):
                        try:
                            raw = await store.read_file(project_id, norm)
                            files_backup[norm] = raw.decode("utf-8")
                        except Exception:
                            files_backup[norm] = f.get("content", "")
                    else:
                        files_backup[norm] = f.get("content", "")

        return ProjectSnapshot(
            project_id=project_id,
            timestamp=time.time(),
            files_backup=files_backup
        )

    async def rollback_snapshot(self, project_id: str, snapshot: ProjectSnapshot, memory_files: List[dict]) -> List[dict]:
        """Restores project files on disk and memory back to the snapshot state."""
        logger.info(f"Rolling back project {project_id} to snapshot taken at {snapshot.timestamp}")
        store = get_artifact_store()
        
        # 1. Restore disk files
        for rel_path, content in snapshot.files_backup.items():
            try:
                await store.write_file(project_id, rel_path, content)
            except Exception as e:
                logger.error(f"Rollback file write error for {rel_path}: {e}")

        # 2. Restore memory files array
        restored_memory = []
        for rel_path, content in snapshot.files_backup.items():
            restored_memory.append({"path": rel_path, "content": content})
            
        return restored_memory

    async def apply_patch(
        self,
        project_id: str,
        patch_result: PatchResult,
        memory_files: List[dict],
        attempt: int = 1,
        execution_id: Optional[str] = None
    ) -> Tuple[PatchApplyResult, List[dict]]:
        
        # Cancellation checkpoint immediately before patch application
        if execution_id:
            from app.services.redis_coordinator import redis_coordinator
            from app.services.task_queue import ExecutionCancelledError
            if await redis_coordinator.is_cancelled(execution_id):
                logger.info(f"Cancellation requested before applying patch for execution {execution_id}. Aborting patch application.")
                raise ExecutionCancelledError(f"Cancellation requested before applying patch for execution {execution_id}")

        errors = []

        # Step 1: Pre-Validation (Atomic Security Gate)
        if not patch_result or patch_result.status != "PATCH_READY":
            errors.append(f"Patch status is '{getattr(patch_result, 'status', 'NULL')}', expected 'PATCH_READY'")

        if patch_result and not patch_result.changes:
            errors.append("Patch contains 0 changes")

        if patch_result and len(patch_result.changes) > MAX_PATCH_FILES:
            errors.append(f"Patch exceeds max changed files limit ({MAX_PATCH_FILES})")

        seen_paths = set()

        if patch_result:
            for change in patch_result.changes:
                raw_path = change.path
                norm_path = raw_path.lstrip("/").lstrip("\\").replace("\\", "/")

                # Path Security Gate
                if ".." in raw_path or raw_path.startswith("/") or raw_path.startswith("\\") or ":" in raw_path:
                    errors.append(f"Path traversal or absolute path rejected: {raw_path}")

                if norm_path in seen_paths:
                    errors.append(f"Duplicate target path in patch: {raw_path}")
                seen_paths.add(norm_path)

                if change.action.lower() not in ALLOWED_ACTIONS:
                    errors.append(f"Unsupported action '{change.action}' for path: {raw_path}")

                if len(change.content or "") > MAX_FILE_PATCH_CHARS:
                    errors.append(f"File content exceeds {MAX_FILE_PATCH_CHARS} limit for path: {raw_path}")

        # If ANY validation error occurs, ABORT IMMEDIATELY (Atomicity guarantee: 0 files written)
        if errors:
            logger.warning(f"Patch application rejected for project {project_id}: {errors}")
            return PatchApplyResult(
                status="REJECTED",
                attempt=attempt,
                errors=errors
            ), memory_files

        # 1. Capture snapshot before applying
        snapshot = await self.create_snapshot(project_id, memory_files)

        # Step 2: Atomic Execution Phase
        modified_files = []
        created_files = []
        updated_memory = [dict(f) for f in memory_files] if isinstance(memory_files, list) else []

        memory_index = {
            f["path"].lstrip("/").lstrip("\\").replace("\\", "/"): idx
            for idx, f in enumerate(updated_memory)
            if isinstance(f, dict) and f.get("path")
        }

        patch_hash = compute_patch_hash(patch_result.changes)
        store = get_artifact_store()
        apply_errors = []

        for change in patch_result.changes:
            norm_path = change.path.lstrip("/").lstrip("\\").replace("\\", "/")
            new_content = change.content

            try:
                await store.write_file(project_id, norm_path, new_content)
            except Exception as write_err:
                logger.error(f"Failed writing file {norm_path}: {write_err}")
                apply_errors.append(f"Failed writing {norm_path}")
                break # Stop on first error

            # Update memory files
            if norm_path in memory_index:
                idx = memory_index[norm_path]
                updated_memory[idx]["content"] = new_content
                modified_files.append(norm_path)
            else:
                updated_memory.append({"path": norm_path, "content": new_content})
                created_files.append(norm_path)

        if apply_errors:
            logger.warning(f"Patch apply failed midway for {project_id}, rolling back. Errors: {apply_errors}")
            updated_memory = await self.rollback_snapshot(project_id, snapshot, memory_files)
            return PatchApplyResult(status="REJECTED", attempt=attempt, errors=apply_errors), updated_memory

        res = PatchApplyResult(
            status="APPLIED",
            modified_files=modified_files,
            created_files=created_files,
            patch_hash=patch_hash,
            attempt=attempt,
            errors=[]
        )
        return res, updated_memory
