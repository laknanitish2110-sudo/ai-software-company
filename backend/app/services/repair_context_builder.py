import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.models.execution_schema import (
    RepairContext,
    MissingFileError,
    DefinitionOfDone,
    ExecutionPlan
)
from app.services.sandbox_runner import ExecutionResult, StageResult
from app.agents.qa import QAReport
from app.services.file_generator import PROJECTS_DIR

logger = logging.getLogger(__name__)

# Max limits to prevent LLM prompt context window bloat
MAX_AFFECTED_FILES = 5
MAX_TOTAL_FILE_CONTENT_CHARS = 50000


class RepairContextBuilder:
    """
    Builds a controlled, bounded RepairContext payload for future repair agents.
    Reuses existing generated file storage and enforces path security and context size limits.
    """
    def __init__(self, project_id: str, attempt: int = 1):
        self.project_id = project_id
        self.attempt = attempt

    def build(
        self,
        qa_report: QAReport,
        exec_result: ExecutionResult,
        dod: DefinitionOfDone,
        engineer_output: Optional[dict] = None,
        architect_output: Optional[dict] = None,
        previous_attempts: Optional[List[dict]] = None
    ) -> RepairContext:
        
        # 1. Base metadata
        ctx = RepairContext(
            project_id=self.project_id,
            execution_id=exec_result.execution_id if exec_result else "",
            attempt=self.attempt,
            definition_of_done=dod,
            failed_stage=exec_result.failed_stage if exec_result else "UNKNOWN",
            failure_category=qa_report.failure_category,
            error_signature=(exec_result.error_signature if (exec_result and exec_result.error_signature) else ""),
            qa_report=qa_report.model_dump() if hasattr(qa_report, "model_dump") else qa_report.dict(),
            previous_attempts=previous_attempts or []
        )

        # 2. Extract failure log snippet
        if exec_result and exec_result.failed_stage:
            st_info: StageResult = exec_result.stages.get(exec_result.failed_stage, StageResult())
            ctx.error_snippet = st_info.stderr_snippet or st_info.stdout_snippet or qa_report.root_cause

        # 3. Extract concise architecture constraints
        if architect_output and isinstance(architect_output, dict):
            ctx.architecture_constraints = {
                "tech_stack": architect_output.get("tech_stack", []),
                "backend_architecture": architect_output.get("backend_architecture", {}),
                "frontend_architecture": architect_output.get("frontend_architecture", {})
            }

        # 4. Resolve affected files with path security and missing file errors
        affected_paths = list(qa_report.affected_files or [])
        if engineer_output and isinstance(engineer_output, dict):
            eng_files = [f.get("path") for f in engineer_output.get("files", []) if isinstance(f, dict) and f.get("path")]
            if not affected_paths:
                affected_paths = eng_files
            else:
                # Include non-test source files in affected_paths so targeted repairs hit implementation files
                for p in eng_files:
                    if p and not p.startswith("test_") and not p.endswith("_test.py") and p not in affected_paths:
                        affected_paths.append(p)
        ctx.affected_file_paths = affected_paths

        # Index available files in memory engineer_output if present
        memory_files_map = {}
        if engineer_output and isinstance(engineer_output, dict):
            for f in engineer_output.get("files", []):
                if isinstance(f, dict) and f.get("path"):
                    norm = f["path"].lstrip("/").lstrip("\\").replace("\\", "/")
                    memory_files_map[norm] = f.get("content", "")

        project_dir = (PROJECTS_DIR / self.project_id).resolve()
        has_disk_dir = project_dir.exists()

        # Prioritize affected paths first, then remaining project files from codebase
        all_candidate_paths = list(affected_paths)
        for p in memory_files_map.keys():
            if p not in all_candidate_paths:
                all_candidate_paths.append(p)

        total_chars = 0
        file_count = 0

        for raw_path in all_candidate_paths:
            if file_count >= MAX_AFFECTED_FILES:
                logger.warning(f"Exceeded max affected files limit ({MAX_AFFECTED_FILES}), skipping remaining.")
                break

            norm_path = raw_path.lstrip("/").lstrip("\\").replace("\\", "/")
            
            # Security Check: Path Traversal
            if ".." in norm_path or norm_path.startswith("/") or ":" in norm_path:
                ctx.missing_files.append(MissingFileError(
                    path=raw_path,
                    error="Path traversal or invalid path attempt rejected",
                    security_flag=True
                ))
                continue

            content = None

            # Check disk storage first if available
            if has_disk_dir:
                try:
                    target_file = (project_dir / norm_path).resolve()
                    if target_file.is_relative_to(project_dir) and target_file.exists() and target_file.is_file():
                        content = target_file.read_text(encoding="utf-8", errors="ignore")
                    elif not target_file.is_relative_to(project_dir):
                        ctx.missing_files.append(MissingFileError(
                            path=raw_path,
                            error="Path traversal attempt rejected",
                            security_flag=True
                        ))
                        continue
                except Exception as e:
                    logger.debug(f"Disk read check error for {norm_path}: {e}")

            # Check memory files if not found on disk
            if content is None and norm_path in memory_files_map:
                content = memory_files_map[norm_path]

            if content is not None:
                # Check character limit
                if total_chars + len(content) > MAX_TOTAL_FILE_CONTENT_CHARS:
                    avail_chars = MAX_TOTAL_FILE_CONTENT_CHARS - total_chars
                    if avail_chars > 200:
                        content = content[:avail_chars] + "\n... [truncated file content] ..."
                    else:
                        break
                ctx.file_contents[norm_path] = content
                total_chars += len(content)
                file_count += 1
            else:
                ctx.missing_files.append(MissingFileError(
                    path=raw_path,
                    error="File does not exist in project codebase",
                    security_flag=False
                ))

        return ctx


def build_repair_context(
    project_id: str,
    qa_report: QAReport,
    exec_result: ExecutionResult,
    dod: DefinitionOfDone,
    engineer_output: Optional[dict] = None,
    architect_output: Optional[dict] = None,
    attempt: int = 1,
    previous_attempts: Optional[List[dict]] = None
) -> RepairContext:
    builder = RepairContextBuilder(project_id=project_id, attempt=attempt)
    return builder.build(
        qa_report=qa_report,
        exec_result=exec_result,
        dod=dod,
        engineer_output=engineer_output,
        architect_output=architect_output,
        previous_attempts=previous_attempts
    )
