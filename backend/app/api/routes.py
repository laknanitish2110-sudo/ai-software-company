import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.models.schemas import (
    CreateProjectRequest,
    ApprovalRequest,
    CallEmployeeRequest,
    AgentRole,
)
from app.services.orchestrator import orchestrator
from app.services.file_generator import get_project_zip_path, get_generated_files_list, generate_project_files
from app.services.pptx_generator import get_pptx_path, generate_pptx
from app.services.docx_generator import get_docx_path, generate_docx
from app.services.workflow_generator import get_workflow_json_path, generate_workflow_json
from app.services.webhook import send_share_request
from app.services.demo_cache import save_demo, load_demo, has_demo, get_demo_deliverable
from app.core.config import N8N_WEBHOOK_URL
from app.core.database import (
    get_project,
    get_project_outputs,
    get_memory,
    list_projects,
    get_conversation,
    get_db,
    new_id,
    now_iso,
)
from app.agents.engine import call_employee
from app.services.workflow_search import (
    analyze_for_problem,
    search_workflows,
    search_by_category,
    get_category_stats,
    get_workflow_detail,
)

router = APIRouter()

active_connections: dict[str, list[WebSocket]] = {}


async def ws_broadcast(msg_type: str, project_id: str, data: dict):
    message = json.dumps({"type": msg_type, "project_id": project_id, "data": data})
    connections = active_connections.get(project_id, [])
    dead = []
    for ws in connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections.remove(ws)


orchestrator.set_ws_callback(ws_broadcast)


@router.post("/projects")
async def create_project(req: CreateProjectRequest):
    project = await orchestrator.start_project(req.problem_statement, auto_approve=req.auto_approve)
    return project


@router.get("/projects")
async def get_projects():
    return await list_projects()


@router.get("/projects/{project_id}")
async def get_project_detail(project_id: str):
    state = await orchestrator.get_project_state(project_id)
    if not state:
        raise HTTPException(404, "Project not found")
    return state


@router.get("/projects/{project_id}/outputs")
async def get_outputs(project_id: str):
    return await get_project_outputs(project_id)


@router.get("/projects/{project_id}/memory")
async def get_project_memory(project_id: str):
    return await get_memory(project_id)


@router.post("/projects/{project_id}/approve/{output_id}")
async def approve_output(project_id: str, output_id: str, req: ApprovalRequest):
    await orchestrator.handle_approval(project_id, output_id, req.approved, req.feedback)
    return {"status": "ok", "approved": req.approved}


@router.post("/projects/{project_id}/call")
async def call_employee_endpoint(project_id: str, req: CallEmployeeRequest):
    project = await get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    response = await call_employee(project_id, req.role, req.message)
    return {"role": req.role.value, "response": response}


@router.get("/projects/{project_id}/conversation/{role}")
async def get_employee_conversation(project_id: str, role: str):
    try:
        agent_role = AgentRole(role)
    except ValueError:
        raise HTTPException(400, f"Invalid role: {role}")
    messages = await get_conversation(project_id, agent_role.value)
    return {"role": role, "messages": messages}


@router.get("/projects/{project_id}/introspection/{role}")
async def get_agent_introspection(project_id: str, role: str):
    from app.agents.engine import SYSTEM_PROMPTS, ROLE_LABELS, AGENT_TIMEOUTS
    from app.core.config import MODEL_MAP, SMART_MODEL, PROVIDER_MAP

    try:
        agent_role = AgentRole(role)
    except ValueError:
        raise HTTPException(400, f"Invalid role: {role}")

    memory = await get_memory(project_id)

    timing = {}
    ikey = f"introspection_{role}"
    if ikey in memory:
        try:
            timing = json.loads(memory[ikey])
        except Exception:
            pass

    peer_review = None
    prkey = f"peer_review_{role}"
    if prkey in memory:
        try:
            peer_review = json.loads(memory[prkey])
        except Exception:
            pass

    from app.core.database import get_latest_output
    output = await get_latest_output(project_id, role)

    return {
        "role": role,
        "label": ROLE_LABELS.get(agent_role, role),
        "model": MODEL_MAP.get(role, SMART_MODEL),
        "provider": PROVIDER_MAP.get(role, "openrouter"),
        "system_prompt": SYSTEM_PROMPTS.get(agent_role, ""),
        "max_tokens": {AgentRole.CEO: 8192, AgentRole.BUSINESS_ANALYST: 16384, AgentRole.RESEARCHER: 8192, AgentRole.ARCHITECT: 16384, AgentRole.ENGINEER: 32000, AgentRole.PPT: 8192}.get(agent_role, 8192),
        "timeout": AGENT_TIMEOUTS.get(agent_role, 120),
        "timing": timing,
        "output": output,
        "peer_review": peer_review,
    }


@router.get("/projects/{project_id}/download/code")
async def download_code(project_id: str):
    zip_path = get_project_zip_path(project_id)
    if not zip_path:
        zip_path = get_demo_deliverable("zip")
    if not zip_path:
        raise HTTPException(404, "No generated files found. Engineer must complete first.")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"project-{project_id}.zip",
    )


@router.get("/projects/{project_id}/download/pptx")
async def download_pptx(project_id: str):
    pptx_path = get_pptx_path(project_id)
    if not pptx_path:
        pptx_path = get_demo_deliverable("pptx")
    if not pptx_path:
        raise HTTPException(404, "No presentation found. PPT agent must complete first.")
    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"project-{project_id}-presentation.pptx",
    )


@router.get("/projects/{project_id}/download/docx")
async def download_docx(project_id: str):
    docx_path = get_docx_path(project_id)
    if not docx_path:
        docx_path = get_demo_deliverable("docx")
    if not docx_path:
        raise HTTPException(404, "No report found. Project must complete first.")
    return FileResponse(
        docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"project-{project_id}-report.docx",
    )


@router.get("/projects/{project_id}/download/workflow")
async def download_workflow(project_id: str):
    wf_path = get_workflow_json_path(project_id)
    if not wf_path:
        wf_path = get_demo_deliverable("workflow")
    if not wf_path:
        raise HTTPException(404, "No workflow JSON found. Engineer must complete with deliverable_type 'workflow' or 'hybrid'.")
    return FileResponse(
        wf_path,
        media_type="application/json",
        filename=f"project-{project_id}-workflow.json",
    )


@router.get("/projects/{project_id}/files")
async def list_generated_files(project_id: str):
    files = get_generated_files_list(project_id)
    return {"project_id": project_id, "files": files, "count": len(files)}


@router.get("/projects/{project_id}/files/content")
async def get_file_contents(project_id: str):
    from app.services.file_generator import get_generated_file_contents
    files = get_generated_file_contents(project_id)
    return {"project_id": project_id, "files": files, "count": len(files)}


class ShareRequest(BaseModel):
    share_type: str  # "drive", "sheets", "email", "all"


@router.get("/integrations/status")
async def integration_status():
    return {
        "n8n_connected": bool(N8N_WEBHOOK_URL),
        "webhook_url_set": bool(N8N_WEBHOOK_URL),
    }


@router.post("/projects/{project_id}/share")
async def share_project(project_id: str, req: ShareRequest):
    project = await get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if not N8N_WEBHOOK_URL:
        raise HTTPException(
            400,
            "n8n webhook URL not configured. Set N8N_WEBHOOK_URL in .env to enable sharing.",
        )

    outputs = await get_project_outputs(project_id)
    memory = await get_memory(project_id)

    file_paths = {}
    if req.share_type in ("drive", "all"):
        zip_path = get_project_zip_path(project_id)
        pptx_path = get_pptx_path(project_id)
        docx_path = get_docx_path(project_id)
        if zip_path:
            file_paths["code_zip"] = zip_path
        if pptx_path:
            file_paths["presentation"] = pptx_path
        if docx_path:
            file_paths["report"] = docx_path

    await send_share_request(
        project_id=project_id,
        share_type=req.share_type,
        project_data=project,
        outputs=outputs,
        memory=memory,
        file_paths=file_paths if file_paths else None,
    )

    return {
        "status": "sent",
        "share_type": req.share_type,
        "message": f"Project data sent to n8n for {req.share_type} sharing.",
    }


@router.post("/demo/save/{project_id}")
async def save_demo_cache(project_id: str):
    result = await save_demo(project_id)
    return result


@router.get("/demo/load")
async def load_demo_cache():
    data = load_demo()
    if not data:
        raise HTTPException(404, "No demo cache found. Run a successful pipeline first, then save it.")

    project = data.get("project", {})
    pid = project.get("id", "")
    existing = await get_project(pid)
    if not existing:
        db = await get_db()
        try:
            ts = project.get("created_at", now_iso())
            await db.execute(
                "INSERT INTO projects (id, problem_statement, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (pid, project.get("problem_statement", ""), project.get("status", "completed"), ts, project.get("updated_at", ts)),
            )
            for out in data.get("outputs", []):
                await db.execute(
                    "INSERT OR IGNORE INTO agent_outputs (id, project_id, role, content, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (out.get("id", new_id()), pid, out.get("role", ""), json.dumps(out.get("content", {})) if isinstance(out.get("content"), dict) else out.get("content", "{}"), out.get("status", "approved"), out.get("created_at", ts)),
                )
            for key, value in data.get("memory", {}).items():
                await db.execute(
                    "INSERT OR IGNORE INTO shared_memory (id, project_id, key, value, updated_by, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (new_id(), pid, key, value if isinstance(value, str) else json.dumps(value), "demo", ts),
                )
            await db.commit()
        finally:
            await db.close()

        for out in data.get("outputs", []):
            if out.get("role") == "engineer" and isinstance(out.get("content"), dict):
                eng = out["content"]
                raw_files = eng.get("files", {})
                if isinstance(raw_files, dict):
                    eng["files"] = [{"path": p, "content": c} for p, c in raw_files.items() if isinstance(c, str)]
                try:
                    generate_project_files(pid, eng)
                except Exception:
                    pass
                try:
                    generate_workflow_json(pid, eng)
                except Exception:
                    pass
            if out.get("role") == "ppt" and isinstance(out.get("content"), dict):
                try:
                    generate_pptx(pid, out["content"])
                except Exception:
                    pass
        try:
            generate_docx(pid, project, data.get("outputs", []), data.get("memory", {}))
        except Exception:
            pass

    return data


@router.get("/demo/status")
async def demo_status():
    return {"has_demo": has_demo()}


@router.get("/demo/download/{file_type}")
async def download_demo_deliverable(file_type: str):
    path = get_demo_deliverable(file_type)
    if not path:
        raise HTTPException(404, f"No cached {file_type} found")
    media_types = {
        "zip": "application/zip",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return FileResponse(path, media_type=media_types.get(file_type, "application/octet-stream"), filename=f"demo-project.{file_type}")


# --- Workflow RAG endpoints ---

class WorkflowSearchRequest(BaseModel):
    query: str
    limit: int = 10
    category: str | None = None
    ai_only: bool = False


@router.post("/workflows/analyze")
async def analyze_workflows(req: WorkflowSearchRequest):
    """RAG entry point — takes a problem statement, returns categorized workflow matches."""
    return analyze_for_problem(req.query, limit=req.limit)


@router.get("/workflows/search")
async def search_workflow_index(q: str, limit: int = 10, category: str | None = None, ai_only: bool = False):
    return search_workflows(q, limit=limit, category=category, ai_only=ai_only)


@router.get("/workflows/categories")
async def workflow_categories():
    return get_category_stats()


@router.get("/workflows/category/{category}")
async def workflows_by_category(category: str, limit: int = 20, ai_only: bool = False):
    return search_by_category(category, limit=limit, ai_only=ai_only)


@router.get("/workflows/{workflow_id}")
async def workflow_detail(workflow_id: int):
    result = get_workflow_detail(workflow_id)
    if not result:
        raise HTTPException(404, "Workflow not found")
    return result


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    if project_id not in active_connections:
        active_connections[project_id] = []
    active_connections[project_id].append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections[project_id].remove(websocket)
        if not active_connections[project_id]:
            del active_connections[project_id]
