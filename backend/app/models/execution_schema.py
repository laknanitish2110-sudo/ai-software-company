from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DoDItem(BaseModel):
    id: str
    description: str
    verification_type: str = "manual_review"  # build, test, runtime, health_check, manual_review
    required: bool = True


class DefinitionOfDone(BaseModel):
    items: List[DoDItem] = Field(default_factory=list)


class MissingFileError(BaseModel):
    path: str
    error: str = "File does not exist in project codebase"
    security_flag: bool = False


class RepairContext(BaseModel):
    project_id: str
    execution_id: str = ""
    attempt: int = 1
    definition_of_done: DefinitionOfDone = Field(default_factory=DefinitionOfDone)
    architecture_constraints: Dict[str, Any] = Field(default_factory=dict)
    qa_report: Dict[str, Any] = Field(default_factory=dict)
    failed_stage: str = "UNKNOWN"
    failure_category: str = "UNKNOWN"
    error_signature: str = ""
    error_snippet: str = ""
    affected_file_paths: List[str] = Field(default_factory=list)
    file_contents: Dict[str, str] = Field(default_factory=dict)
    missing_files: List[MissingFileError] = Field(default_factory=list)
    previous_attempts: List[Dict[str, Any]] = Field(default_factory=list)


class FilePatch(BaseModel):
    path: str
    action: str = "modify"  # "modify", "create" ("delete" is disabled in V1 for security)
    content: str = ""
    reason: str = ""


class PatchResult(BaseModel):
    status: str = "PATCH_READY"  # PATCH_READY, NO_PATCH_POSSIBLE, PREVIOUS_PATCH_FAILED, PATCH_REJECTED
    changes: List[FilePatch] = Field(default_factory=list)
    reason: str = ""
    confidence: float = 1.0
    validation_errors: List[str] = Field(default_factory=list)


class ProjectSnapshot(BaseModel):
    project_id: str
    timestamp: float = 0.0
    files_backup: Dict[str, str] = Field(default_factory=dict)


class PatchApplyResult(BaseModel):
    status: str = "APPLIED"  # APPLIED, REJECTED, FAILED
    modified_files: List[str] = Field(default_factory=list)
    created_files: List[str] = Field(default_factory=list)
    patch_hash: str = ""
    attempt: int = 1
    errors: List[str] = Field(default_factory=list)


class ExecutionBaseline(BaseModel):
    project_id: str = ""
    overall_status: str = "UNKNOWN"
    failed_stage: Optional[str] = None
    stage_statuses: Dict[str, str] = Field(default_factory=dict)
    passed_checks: List[str] = Field(default_factory=list)
    failed_checks: List[str] = Field(default_factory=list)
    error_signatures: Dict[str, str] = Field(default_factory=dict)


class RegressionResult(BaseModel):
    status: str = "SAFE_TO_ACCEPT"  # SAFE_TO_ACCEPT, REGRESSION, REPAIR_FAILED
    fixed_failures: List[str] = Field(default_factory=list)
    regressions: List[str] = Field(default_factory=list)
    new_failures: List[str] = Field(default_factory=list)
    unchanged_failures: List[str] = Field(default_factory=list)
    safe_to_accept: bool = True
    reason: str = ""


class RepairAttempt(BaseModel):
    attempt: int
    execution_id: str = ""
    qa_status: str = "FAIL"
    failure_category: str = "UNKNOWN"
    patch_hash: str = ""
    patch_status: str = "NONE"
    post_execution_status: str = "NONE"
    regression_status: str = "NONE"
    reason: str = ""


class FinalValidationResult(BaseModel):
    attempts_used: int = 1
    final_status: str = "VALIDATED"  # VALIDATED, VALIDATION_FAILED
    final_execution_result: Optional[Dict[str, Any]] = None
    final_qa_report: Optional[Dict[str, Any]] = None
    repair_history: List[RepairAttempt] = Field(default_factory=list)
    regression_results: List[Dict[str, Any]] = Field(default_factory=list)
    reason: str = ""


class HealthCheckSpec(BaseModel):
    type: str = "http"
    path: str = "/"
    port: int = 3000
    expected_status: int = 200
    timeout_seconds: int = 15


class ExecutionCommands(BaseModel):
    install: Optional[str] = None
    build: Optional[str] = None
    test: Optional[str] = None
    start: Optional[str] = None
    health_check: Optional[HealthCheckSpec] = None


class ExecutionEnvironment(BaseModel):
    node_version: str = "20"
    python_version: str = "3.11"
    env_vars: Dict[str, str] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    project_type: str = "node"  # node, python, n8n, hybrid, unknown
    primary_language: str = "javascript"
    executable: bool = True
    execution_reason: Optional[str] = None
    environment: ExecutionEnvironment = Field(default_factory=ExecutionEnvironment)
    commands: ExecutionCommands = Field(default_factory=ExecutionCommands)


def parse_or_convert_dod(ba_output: dict, plan: Optional[ExecutionPlan] = None) -> DefinitionOfDone:
    """
    Extends/converts existing BA acceptance_criteria or definition_of_done into structured DoD.
    Does NOT create a parallel requirements system.
    """
    raw_dod = ba_output.get("definition_of_done") or ba_output.get("acceptance_criteria") or []
    
    parsed_items = []
    
    # 1. If already structured list of dicts
    if isinstance(raw_dod, list):
        for idx, item in enumerate(raw_dod, start=1):
            if isinstance(item, dict):
                try:
                    dod_item = DoDItem.model_validate(item)
                    parsed_items.append(dod_item)
                except Exception:
                    pass
            elif isinstance(item, str) and item.strip():
                # Convert string criteria to DoD item
                text = item.strip()
                vtype = "manual_review"
                
                # Classify based on text keywords
                lower_text = text.lower()
                if "build" in lower_text or "compile" in lower_text:
                    vtype = "build"
                elif "test" in lower_text or "unit" in lower_text or "spec" in lower_text:
                    vtype = "test"
                elif "start" in lower_text or "run" in lower_text or "launch" in lower_text:
                    vtype = "runtime"
                elif "health" in lower_text or "http" in lower_text or "200" in lower_text or "endpoint" in lower_text or "api" in lower_text:
                    vtype = "health_check"

                parsed_items.append(DoDItem(
                    id=f"AC-{idx}",
                    description=text,
                    verification_type=vtype,
                    required=True
                ))

    # 2. Automatically ensure base execution criteria are present if plan is executable
    if plan and plan.executable:
        has_build = any(i.verification_type == "build" for i in parsed_items)
        has_health = any(i.verification_type == "health_check" for i in parsed_items)
        
        if not has_build and plan.commands.build:
            parsed_items.insert(0, DoDItem(
                id="AC-BUILD",
                description="Project build/compilation succeeds cleanly without syntax errors.",
                verification_type="build",
                required=True
            ))
        if not has_health and plan.commands.health_check:
            parsed_items.append(DoDItem(
                id="AC-HEALTH",
                description="Application starts and responds to HTTP health check probe.",
                verification_type="health_check",
                required=True
            ))

    return DefinitionOfDone(items=parsed_items)


def validate_and_detect_execution_plan(engineer_output: dict) -> ExecutionPlan:
    """
    Validates declared runtime_manifest in engineer_output or auto-detects
    execution commands from files list and project metadata.
    """
    manifest_data = engineer_output.get("runtime_manifest") or engineer_output.get("execution_plan")
    
    files = engineer_output.get("files", [])
    file_paths = [f.get("path", "").lower() for f in files if isinstance(f, dict)]
    
    # 1. Check if n8n workflow deliverable only
    is_workflow_only = bool(
        engineer_output.get("n8n_workflow") and not files
    ) or engineer_output.get("deliverable_type") == "workflow"

    if is_workflow_only and not files:
        return ExecutionPlan(
            project_type="n8n",
            primary_language="json",
            executable=False,
            execution_reason="n8n workflow JSON deliverable — import directly into n8n.",
            commands=ExecutionCommands()
        )

    # 2. Parse declared manifest if present
    if isinstance(manifest_data, dict):
        try:
            plan = ExecutionPlan.model_validate(manifest_data)
            return plan
        except Exception:
            pass

    # 3. Auto-detect based on generated files
    has_package_json = any("package.json" in fp for fp in file_paths)
    has_requirements_txt = any("requirements.txt" in fp or "pyproject.toml" in fp for fp in file_paths)
    has_python_files = any(fp.endswith(".py") for fp in file_paths)
    has_node_files = any(fp.endswith((".js", ".ts", ".jsx", ".tsx")) for fp in file_paths)

    if has_package_json or (has_node_files and not has_python_files):
        project_type = "node"
        primary_language = "typescript" if any(fp.endswith((".ts", ".tsx")) for fp in file_paths) else "javascript"
        
        # Check if Next.js or React
        is_next = any("next" in fp for fp in file_paths) or any("package.json" in fp for fp in file_paths)
        
        install_cmd = "npm install"
        build_cmd = "npm run build" if is_next else None
        test_cmd = "npm test -- --passWithNoTests"
        start_cmd = "npm start"
        health_port = 3000
        
        # Extract scripts from package.json if present
        for f in files:
            if isinstance(f, dict) and "package.json" in f.get("path", ""):
                try:
                    pkg = json.loads(f.get("content", "{}"))
                    scripts = pkg.get("scripts", {})
                    if "build" in scripts:
                        build_cmd = "npm run build"
                    if "test" in scripts:
                        test_cmd = "npm test"
                    if "start" in scripts:
                        start_cmd = "npm start"
                    elif "dev" in scripts:
                        start_cmd = "npm run dev"
                except Exception:
                    pass

        return ExecutionPlan(
            project_type=project_type,
            primary_language=primary_language,
            executable=True,
            environment=ExecutionEnvironment(node_version="20", env_vars={"PORT": str(health_port), "NODE_ENV": "development"}),
            commands=ExecutionCommands(
                install=install_cmd,
                build=build_cmd,
                test=test_cmd,
                start=start_cmd,
                health_check=HealthCheckSpec(type="http", path="/", port=health_port, expected_status=200)
            )
        )

    elif has_requirements_txt or has_python_files:
        project_type = "python"
        primary_language = "python"
        
        install_cmd = "pip install -r requirements.txt" if has_requirements_txt else "pip install fastapi uvicorn"
        
        main_py = "main.py"
        for fp in file_paths:
            if fp.endswith("app.py"):
                main_py = "app.py"
                break

        build_cmd = f"python -m py_compile {main_py}"
        test_cmd = "pytest" if any("test" in fp for fp in file_paths) else None
        start_cmd = f"uvicorn {main_py[:-3]}:app --host 0.0.0.0 --port 8000"
        health_port = 8000

        return ExecutionPlan(
            project_type=project_type,
            primary_language=primary_language,
            executable=True,
            environment=ExecutionEnvironment(python_version="3.11", env_vars={"PORT": str(health_port)}),
            commands=ExecutionCommands(
                install=install_cmd,
                build=build_cmd,
                test=test_cmd,
                start=start_cmd,
                health_check=HealthCheckSpec(type="http", path="/health" if any("health" in f.get("content", "").lower() for f in files if isinstance(f, dict)) else "/", port=health_port, expected_status=200)
            )
        )

    # Hybrid or unknown fallback
    return ExecutionPlan(
        project_type="hybrid" if (engineer_output.get("n8n_workflow") and files) else "unknown",
        primary_language="javascript",
        executable=bool(files),
        execution_reason="Auto-detected execution plan",
        commands=ExecutionCommands(
            install="npm install",
            build=None,
            test=None,
            start="npm start",
            health_check=HealthCheckSpec(type="http", path="/", port=3000, expected_status=200)
        )
    )
