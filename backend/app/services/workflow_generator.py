"""
Generates downloadable n8n workflow JSON files from Engineer output.
"""

import json
from pathlib import Path

PROJECTS_DIR = Path("generated_projects")


def generate_workflow_json(project_id: str, engineer_output: dict) -> str | None:
    n8n_workflow = engineer_output.get("n8n_workflow")
    if not n8n_workflow:
        return None

    PROJECTS_DIR.mkdir(exist_ok=True)
    workflow_name = engineer_output.get("workflow_name", "workflow")
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in workflow_name)
    safe_name = safe_name.strip().replace(" ", "_") or "workflow"

    out_path = PROJECTS_DIR / f"{project_id}_workflow.json"
    out_path.write_text(json.dumps(n8n_workflow, indent=2), encoding="utf-8")
    return str(out_path)


def get_workflow_json_path(project_id: str) -> str | None:
    path = PROJECTS_DIR / f"{project_id}_workflow.json"
    if path.exists():
        return str(path)
    return None
