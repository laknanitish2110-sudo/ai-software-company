import json
import os
import shutil
from pathlib import Path

from app.core.database import get_project, get_project_outputs, get_memory

DEMO_DIR = Path(__file__).parent.parent.parent / "demo_cache"


async def save_demo(project_id: str) -> dict:
    DEMO_DIR.mkdir(exist_ok=True)

    project = await get_project(project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    outputs = await get_project_outputs(project_id)
    memory = await get_memory(project_id)

    cache = {
        "project": project,
        "outputs": outputs,
        "memory": memory,
    }

    cache_file = DEMO_DIR / "demo_run.json"
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2, default=str)

    deliverables_src = Path(__file__).parent.parent.parent / "generated" / project_id
    deliverables_dst = DEMO_DIR / "deliverables"
    if deliverables_src.exists():
        if deliverables_dst.exists():
            shutil.rmtree(deliverables_dst)
        shutil.copytree(deliverables_src, deliverables_dst)

    for ext in ["pptx", "docx"]:
        src = Path(__file__).parent.parent.parent / "generated" / f"{project_id}.{ext}"
        if src.exists():
            shutil.copy2(src, DEMO_DIR / f"demo.{ext}")

    zip_src = Path(__file__).parent.parent.parent / "generated" / f"{project_id}.zip"
    if zip_src.exists():
        shutil.copy2(zip_src, DEMO_DIR / "demo.zip")

    wf_src = Path(__file__).parent.parent.parent / "generated_projects" / f"{project_id}_workflow.json"
    if wf_src.exists():
        shutil.copy2(wf_src, DEMO_DIR / "demo_workflow.json")

    return {"status": "saved", "project_id": project_id, "path": str(cache_file)}


def load_demo() -> dict | None:
    cache_file = DEMO_DIR / "demo_run.json"
    if not cache_file.exists():
        return None

    with open(cache_file) as f:
        return json.load(f)


def has_demo() -> bool:
    return (DEMO_DIR / "demo_run.json").exists()


def get_demo_deliverable(file_type: str) -> str | None:
    paths = {
        "zip": DEMO_DIR / "demo.zip",
        "pptx": DEMO_DIR / "demo.pptx",
        "docx": DEMO_DIR / "demo.docx",
        "workflow": DEMO_DIR / "demo_workflow.json",
    }
    path = paths.get(file_type)
    if path and path.exists():
        return str(path)
    return None
