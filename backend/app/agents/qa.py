import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from app.models.execution_schema import DefinitionOfDone, DoDItem
from app.services.sandbox_runner import ExecutionResult, StageResult

logger = logging.getLogger(__name__)


class QARepairInstructions(BaseModel):
    summary: str = ""
    action_items: List[str] = Field(default_factory=list)


class QAReport(BaseModel):
    status: str = "PASS"  # PASS, FAIL
    severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    failed_criteria: List[str] = Field(default_factory=list)
    failure_category: str = "NONE"  # BUILD_FAILURE, TEST_FAILURE, RUNTIME_FAILURE, HEALTH_FAILURE, MANUAL_REVIEW_NEEDED, NONE
    root_cause: str = "All executed criteria passed cleanly."
    affected_files: List[str] = Field(default_factory=list)
    repair_instructions: QARepairInstructions = Field(default_factory=QARepairInstructions)
    confidence: float = 1.0


def evaluate_qa_results(
    dod: DefinitionOfDone,
    exec_result: ExecutionResult,
    problem_statement: str = "",
    arch_summary: str = ""
) -> QAReport:
    """
    Evaluates Sandbox ExecutionResult against Definition of Done criteria.
    Receives minimal targeted context (DoD + ExecutionResult) to avoid prompt bloat.
    """
    report = QAReport()

    if not exec_result:
        report.status = "FAIL"
        report.severity = "CRITICAL"
        report.failure_category = "NO_EXECUTION"
        report.root_cause = "No execution result was produced by the Sandbox runner."
        return report

    # 1. Evaluate Sandbox overall status
    if exec_result.overall_status == "FAILED":
        report.status = "FAIL"
        failed_stage = exec_result.failed_stage or "UNKNOWN"
        stage_info: StageResult = exec_result.stages.get(failed_stage, StageResult())
        
        # Determine failure category and severity
        if failed_stage == "INSTALL":
            report.severity = "HIGH"
            report.failure_category = "DEPENDENCY_INSTALL_ERROR"
            report.root_cause = f"Dependency installation failed with exit code {stage_info.exit_code}: {stage_info.stderr_snippet[:300]}"
        elif failed_stage == "BUILD":
            report.severity = "HIGH"
            report.failure_category = "BUILD_FAILURE"
            report.root_cause = f"Build/compilation failed with exit code {stage_info.exit_code}: {stage_info.stderr_snippet[:300] or stage_info.stdout_snippet[:300]}"
        elif failed_stage == "TEST":
            report.severity = "HIGH"
            report.failure_category = "TEST_FAILURE"
            report.root_cause = f"Automated unit test suite failed: {stage_info.stderr_snippet[:300] or stage_info.stdout_snippet[:300]}"
        elif failed_stage in ("START", "RUNTIME_START"):
            report.severity = "HIGH"
            report.failure_category = "RUNTIME_FAILURE"
            report.root_cause = f"Application failed to start or crashed on launch: {stage_info.stderr_snippet[:300]}"
        elif failed_stage == "HEALTH_CHECK":
            report.severity = "HIGH"
            report.failure_category = "HEALTH_FAILURE"
            report.root_cause = f"Application root/health endpoint did not respond successfully: {stage_info.stderr_snippet[:300] or stage_info.stdout_snippet[:300]}"

        # Extract referenced file paths from stderr/stdout snippets
        import re
        snippet = (stage_info.stderr_snippet or "") + " " + (stage_info.stdout_snippet or "")
        found_paths = re.findall(r'[\w\-\/\\]+\.(?:py|js|ts|jsx|tsx|json)', snippet)
        if found_paths:
            for p in found_paths:
                norm = p.lstrip("/").lstrip("\\").replace("\\", "/")
                if norm not in report.affected_files:
                    report.affected_files.append(norm)

        # Match failed stage against DoD items
        matched_failed_ids = []
        for item in dod.items:
            if not item.required:
                continue
            if item.verification_type == "build" and failed_stage == "BUILD":
                matched_failed_ids.append(item.id)
            elif item.verification_type == "test" and failed_stage == "TEST":
                matched_failed_ids.append(item.id)
            elif item.verification_type == "runtime" and failed_stage in ("START", "RUNTIME_START"):
                matched_failed_ids.append(item.id)
            elif item.verification_type == "health_check" and failed_stage == "HEALTH_CHECK":
                matched_failed_ids.append(item.id)

        if not matched_failed_ids:
            # Add general failure id if specific DoD item wasn't matched
            matched_failed_ids.append(f"DOD-FAIL-{failed_stage}")

        report.failed_criteria = matched_failed_ids
        report.repair_instructions = QARepairInstructions(
            summary=f"Fix {failed_stage} stage failure",
            action_items=[
                f"Inspect and resolve error in stage {failed_stage}: {report.root_cause}",
                "Ensure all required imports and syntax rules are satisfied."
            ]
        )
        report.confidence = 0.95
        return report

    elif exec_result.overall_status == "SKIPPED":
        report.status = "PASS"
        report.severity = "LOW"
        report.failure_category = "SKIPPED"
        report.root_cause = "Project is non-executable (e.g. n8n workflow deliverable only)."
        report.confidence = 1.0
        return report

    # 2. All executed stages passed cleanly
    report.status = "PASS"
    report.severity = "LOW"
    report.failure_category = "NONE"
    report.root_cause = "All automated sandbox execution stages (INSTALL, BUILD, TEST, START, HEALTH_CHECK) passed cleanly."
    report.confidence = 1.0
    return report
