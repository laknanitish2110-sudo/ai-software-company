"""
Generates downloadable n8n workflow JSON files from Engineer output.
"""

import json
from app.core.artifact_store import get_artifact_store

async def generate_workflow_json(project_id: str, engineer_output: dict) -> str | None:
    """
    Extracts the n8n_workflow from the engineer_output and writes it to the ArtifactStore.
    Returns None since there is no local file path to return.
    """
    n8n_workflow = engineer_output.get("n8n_workflow")
    if not n8n_workflow:
        return None

    store = get_artifact_store()
    await store.write_file(project_id, "n8n_workflow.json", json.dumps(n8n_workflow, indent=2))

    return None


def get_workflow_json_path(project_id: str) -> str | None:
    # Deprecated: files are streamed via ArtifactStore
    return None
