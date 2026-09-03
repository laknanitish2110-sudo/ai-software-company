import json
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends

logger = logging.getLogger(__name__)
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
from app.services.workflow_search import (
    analyze_for_problem,
    search_workflows,
    get_category_stats,
    search_by_category,
    get_workflow_detail,
)
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_optional_user,
)
from app.core.database import (
    get_project,
    get_project_for_user,
    create_user,
    get_user_by_email,
    delete_project,
    get_project_outputs,
    get_memory,
    list_projects,
    get_conversation,
    get_db,
    new_id,
    now_iso,
    create_share_link,
    get_project_by_share_token,
    save_agent_output,
    set_memory,
)

router = APIRouter()

active_connections: dict[str, list[WebSocket]] = {}


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


# --- AUTHENTICATION ENDPOINTS ---

@router.post("/auth/register")
async def register(req: RegisterRequest):
    if not req.email or not req.password:
        raise HTTPException(400, "Email and password are required")
    try:
        allowed, retry_after = await rate_limiter.check_rate_limit(user_id=req.email, action="auth", limit=5, window_seconds=60)
        if not allowed:
            return JSONResponse(status_code=429, content={"error": "RATE_LIMITED", "retry_after_seconds": retry_after})
    except Exception:
        pass
    existing = await get_user_by_email(req.email)
    if existing:
        raise HTTPException(400, "User email is already registered")
    pw_hash = hash_password(req.password)
    user = await create_user(req.email, pw_hash)
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return {"user": user, "access_token": token, "token_type": "bearer"}


@router.post("/auth/login")
async def login(req: LoginRequest):
    if not req.email or not req.password:
        raise HTTPException(400, "Email and password are required")
    try:
        allowed, retry_after = await rate_limiter.check_rate_limit(user_id=req.email, action="auth", limit=5, window_seconds=60)
        if not allowed:
            return JSONResponse(status_code=429, content={"error": "RATE_LIMITED", "retry_after_seconds": retry_after})
    except Exception:
        pass
    user = await get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_access_token({"sub": user["id"], "email": user["email"]})
    return {
        "user": {"id": user["id"], "email": user["email"], "created_at": user["created_at"]},
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


# --- HELPER FOR PROJECT OWNERSHIP CHECK ---

async def _verify_project_owner(project_id: str, user_id: str) -> dict:
    project = await get_project_for_user(project_id, user_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


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


from fastapi.responses import JSONResponse, FileResponse
from app.services.rate_limiter import rate_limiter
from app.services.resource_budget import resource_budget, ResourceBudgetExceededError

# --- PROTECTED PROJECT ENDPOINTS ---

@router.post("/projects")
async def create_project_endpoint(req: CreateProjectRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    try:
        allowed, retry_after = await rate_limiter.check_rate_limit(user_id=user_id, action="create")
        if not allowed:
            return JSONResponse(status_code=429, content={"error": "RATE_LIMITED", "retry_after_seconds": retry_after})

        project = await orchestrator.start_project(
            req.problem_statement,
            user_id=user_id,
            auto_approve=req.auto_approve
        )
        return project
    except RedisUnavailableError as e:
        if get_environment() == "production":
            return JSONResponse(
                status_code=503,
                content={"error": "REDIS_UNAVAILABLE", "message": str(e)}
            )
        raise HTTPException(503, str(e))
    except ValueError as e:
        if "PROJECT_EXECUTION_IN_PROGRESS" in str(e):
            return JSONResponse(status_code=409, content={"error": "PROJECT_EXECUTION_IN_PROGRESS", "message": str(e)})
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error creating project for user {user_id}: {e}", exc_info=True)
        raise HTTPException(500, "Internal server error")


from app.services.task_queue import task_queue, STATUS_QUEUED, STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLING, STATUS_CANCELLED
from app.services.redis_coordinator import redis_coordinator, RedisUnavailableError
from app.core.config import get_environment, REDIS_URL

@router.get("/projects/{project_id}/budget")
async def get_project_budget_endpoint(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    return await resource_budget.get_budget_status(project_id)


@router.get("/projects/{project_id}/executions")
async def get_project_executions_endpoint(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    return await task_queue.list_project_executions(project_id, user_id=current_user["id"])


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution_endpoint(execution_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    exec_rec = await task_queue.get_execution(execution_id, user_id=user_id)
    if not exec_rec:
        raise HTTPException(404, "Execution not found or user unauthorized")

    project_id = exec_rec["project_id"]
    await _verify_project_owner(project_id, user_id)

    status = exec_rec["status"]
    if status in (STATUS_COMPLETED, STATUS_FAILED):
        return JSONResponse(
            status_code=400,
            content={"error": "CANNOT_CANCEL_TERMINAL_EXECUTION", "message": f"Cannot cancel execution in terminal state '{status}'"}
        )

    if status in (STATUS_CANCELLING, STATUS_CANCELLED):
        return JSONResponse(
            status_code=200,
            content={"status": status, "message": "Execution is already cancelling or cancelled"}
        )

    if get_environment() == "production" and not REDIS_URL:
        return JSONResponse(
            status_code=503,
            content={"error": "REDIS_UNAVAILABLE", "message": "Cancellation signaling requires Redis in production. Please retry."}
        )

    try:
        await redis_coordinator.set_cancellation_flag(execution_id)
    except RedisUnavailableError as e:
        if get_environment() == "production":
            return JSONResponse(
                status_code=503,
                content={"error": "REDIS_UNAVAILABLE", "message": str(e)}
            )

    try:
        if status == STATUS_QUEUED:
            await task_queue.cancel(execution_id)
            await redis_coordinator.publish_event(project_id, "cancellation_completed", {"execution_id": execution_id})
            return JSONResponse(status_code=200, content={"status": STATUS_CANCELLED, "message": "Queued execution cancelled immediately"})

        await task_queue.mark_cancelling(execution_id, user_id)
        await redis_coordinator.publish_event(project_id, "cancellation_requested", {"execution_id": execution_id})
        return JSONResponse(status_code=202, content={"status": STATUS_CANCELLING, "message": "Cancellation request accepted"})
    except Exception as db_err:
        logger.error(f"PostgreSQL error during cancellation of {execution_id}: {db_err}")
        return JSONResponse(status_code=500, content={"error": "DATABASE_ERROR", "message": "Internal server error"})


@router.get("/projects")
async def get_projects(current_user: dict = Depends(get_current_user)):
    return await list_projects(user_id=current_user["id"])


@router.get("/projects/{project_id}")
async def get_project_detail(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    state = await orchestrator.get_project_state(project_id)
    if not state:
        raise HTTPException(404, "Project not found")
    return state


@router.delete("/projects/{project_id}")
async def delete_project_endpoint(project_id: str, current_user: dict = Depends(get_current_user)):
    deleted = await delete_project(project_id, current_user["id"])
    if not deleted:
        raise HTTPException(404, "Project not found")
    return {"status": "ok", "deleted": True}


@router.get("/projects/{project_id}/outputs")
async def get_outputs(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    return await get_project_outputs(project_id)


@router.get("/projects/{project_id}/memory")
async def get_project_memory(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    return await get_memory(project_id)


@router.post("/projects/{project_id}/approve/{output_id}")
async def approve_output(project_id: str, output_id: str, req: ApprovalRequest, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    await orchestrator.handle_approval(project_id, output_id, req.approved, req.feedback)
    return {"status": "ok", "approved": req.approved}


@router.post("/projects/{project_id}/call")
async def call_employee_endpoint(project_id: str, req: CallEmployeeRequest, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    try:
        allowed, retry_after = await rate_limiter.check_rate_limit(user_id=current_user["id"], action="call")
        if not allowed:
            return JSONResponse(status_code=429, content={"error": "RATE_LIMITED", "retry_after_seconds": retry_after})
    except RedisUnavailableError as e:
        if get_environment() == "production":
            return JSONResponse(
                status_code=503,
                content={"error": "REDIS_UNAVAILABLE", "message": str(e)}
            )
        raise HTTPException(503, str(e))

    from app.agents.engine import call_employee
    try:
        response = await call_employee(project_id, req.role, req.message)
        return {"role": req.role.value, "response": response}
    except Exception as e:
        logger.error(f"Error calling employee {req.role.value} for project {project_id}: {e}", exc_info=True)
        raise HTTPException(500, "Internal server error")


@router.get("/projects/{project_id}/conversation/{role}")
async def get_employee_conversation(project_id: str, role: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    try:
        agent_role = AgentRole(role)
    except ValueError:
        raise HTTPException(400, f"Invalid role: {role}")
    messages = await get_conversation(project_id, agent_role.value)
    return {"role": role, "messages": messages}


@router.get("/projects/{project_id}/introspection/{role}")
async def get_agent_introspection(project_id: str, role: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
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
        "max_tokens": 16000 if agent_role == AgentRole.ENGINEER else 4096,
        "timeout": AGENT_TIMEOUTS.get(agent_role, 120),
        "timing": timing,
        "output": output,
        "peer_review": peer_review,
    }


@router.get("/projects/{project_id}/download/code")
async def download_code(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
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
async def download_pptx(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
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
async def download_docx(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
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
async def download_workflow(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
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
async def list_generated_files(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    files = get_generated_files_list(project_id)
    return {"project_id": project_id, "files": files, "count": len(files)}


@router.get("/projects/{project_id}/files/content")
async def get_file_contents(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    from app.services.file_generator import get_generated_file_contents
    files = get_generated_file_contents(project_id)
    return {"project_id": project_id, "files": files, "count": len(files)}


class ShareRequest(BaseModel):
    share_type: str  # "drive", "sheets", "email", "all"


@router.get("/integrations/status")
async def integration_status(current_user: dict = Depends(get_current_user)):
    return {
        "n8n_connected": bool(N8N_WEBHOOK_URL),
        "webhook_url_set": bool(N8N_WEBHOOK_URL),
    }


@router.post("/projects/{project_id}/share")
async def share_project(project_id: str, req: ShareRequest, current_user: dict = Depends(get_current_user)):
    project = await _verify_project_owner(project_id, current_user["id"])

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


import secrets


class ReviseRequest(BaseModel):
    role: str
    feedback: str


@router.post("/projects/{project_id}/revise")
async def revise_agent_endpoint(project_id: str, req: ReviseRequest, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    try:
        agent_role = AgentRole(req.role)
    except ValueError:
        raise HTTPException(400, f"Invalid role: {req.role}")
    outputs = await get_project_outputs(project_id)
    target_output = None
    for o in reversed(outputs):
        if o["role"] == req.role:
            target_output = o
            break
    if not target_output:
        raise HTTPException(404, f"No output found for role {req.role}")
    await orchestrator.handle_approval(project_id, target_output["id"], approved=False, feedback=req.feedback)
    return {"status": "revision_started", "role": req.role}


@router.post("/projects/{project_id}/share-link")
async def generate_share_link_endpoint(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    token = secrets.token_urlsafe(32)
    await create_share_link(project_id, token)
    return {"token": token}


@router.get("/shared/{token}")
async def get_shared_project(token: str):
    project = await get_project_by_share_token(token)
    if not project:
        raise HTTPException(404, "Shared project not found")
    project_id = project["id"]
    outputs = await get_project_outputs(project_id)
    memory = await get_memory(project_id)
    return {
        "project": dict(project),
        "outputs": outputs,
        "memory": memory,
        "current_agent": None,
        "pending_approval": False,
    }


@router.get("/shared/{token}/download/{file_type}")
async def download_shared_file(token: str, file_type: str):
    project = await get_project_by_share_token(token)
    if not project:
        raise HTTPException(404, "Shared project not found")
    project_id = project["id"]
    if file_type == "code":
        path = get_project_zip_path(project_id) or get_demo_deliverable("zip")
        if not path:
            raise HTTPException(404, "No generated code found")
        return FileResponse(path, media_type="application/zip", filename=f"project-{project_id}.zip")
    elif file_type == "pptx":
        path = get_pptx_path(project_id) or get_demo_deliverable("pptx")
        if not path:
            raise HTTPException(404, "No presentation found")
        return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=f"project-{project_id}.pptx")
    elif file_type == "docx":
        path = get_docx_path(project_id) or get_demo_deliverable("docx")
        if not path:
            raise HTTPException(404, "No report found")
        return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=f"project-{project_id}.docx")
    else:
        raise HTTPException(400, f"Unknown file type: {file_type}")


@router.post("/demo/save/{project_id}")
async def save_demo_cache(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    result = await save_demo(project_id)
    return result


@router.get("/demo/load")
async def load_demo_cache(current_user: dict = Depends(get_current_user)):
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
            await db.commit()
        finally:
            await db.close()

        for out in data.get("outputs", []):
            content = out.get("content", {})
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except Exception:
                    content = {"raw": content}
            await save_agent_output(pid, out.get("role", ""), content)

        for key, value in data.get("memory", {}).items():
            val_str = value if isinstance(value, str) else json.dumps(value)
            await set_memory(pid, key, val_str, "demo")

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
async def download_demo_deliverable(file_type: str, current_user: dict = Depends(get_current_user)):
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
async def websocket_endpoint(websocket: WebSocket, project_id: str, token: str | None = None):
    token_str = token or websocket.query_params.get("token")
    user_id = None
    if token_str:
        payload = decode_access_token(token_str)
        if payload and "sub" in payload:
            user_id = payload["sub"]

    if not user_id:
        await websocket.accept()
        await websocket.close(code=4001, reason="Authentication required")
        return

    project = await get_project_for_user(project_id, user_id)
    if not project:
        print(f"WS DEBUG: project {project_id} not found for user {user_id}")
        await websocket.accept()
        await websocket.close(code=4003, reason="Forbidden")
        return

    await websocket.accept()
    if project_id not in active_connections:
        active_connections[project_id] = []
    active_connections[project_id].append(websocket)

    async def _forward_redis_events():
        try:
            async for event_msg in redis_coordinator.subscribe_events(project_id):
                await websocket.send_text(event_msg)
        except Exception:
            pass

    forward_task = asyncio.create_task(_forward_redis_events())
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        forward_task.cancel()
        if project_id in active_connections and websocket in active_connections[project_id]:
            active_connections[project_id].remove(websocket)
            if not active_connections[project_id]:
                del active_connections[project_id]
