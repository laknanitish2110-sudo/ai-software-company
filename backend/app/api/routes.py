import os
import json
import asyncio
import logging
import secrets
import time
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends

logger = logging.getLogger(__name__)
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse, StreamingResponse
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
from app.core.config import (
    N8N_WEBHOOK_URL,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    OAUTH_FRONTEND_URL, OAUTH_BACKEND_URL,
)
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
    get_user_by_oauth,
    create_oauth_user,
    link_oauth_to_user,
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
        "user": {
            "id": user["id"], "email": user["email"], "created_at": user["created_at"],
            "display_name": user.get("display_name"), "avatar_url": user.get("avatar_url"),
            "oauth_provider": user.get("oauth_provider"),
        },
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


# --- OAuth State Management ---

_oauth_states: dict[str, float] = {}
_OAUTH_STATE_TTL = 300


def _create_oauth_state() -> str:
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = time.time()
    cutoff = time.time() - _OAUTH_STATE_TTL
    for k in [k for k, v in _oauth_states.items() if v < cutoff]:
        del _oauth_states[k]
    return state


def _validate_oauth_state(state: str) -> bool:
    ts = _oauth_states.pop(state, None)
    if ts is None:
        return False
    return (time.time() - ts) < _OAUTH_STATE_TTL


async def _handle_oauth_user(
    email: str, provider: str, provider_id: str,
    display_name: str | None, avatar_url: str | None,
) -> str:
    user = await get_user_by_oauth(provider, provider_id)
    if user:
        return create_access_token({"sub": user["id"], "email": user["email"]})

    user = await get_user_by_email(email)
    if user:
        await link_oauth_to_user(user["id"], provider, provider_id, display_name, avatar_url)
        return create_access_token({"sub": user["id"], "email": user["email"]})

    user = await create_oauth_user(email, provider, provider_id, display_name, avatar_url)
    return create_access_token({"sub": user["id"], "email": user["email"]})


# --- OAuth Endpoints ---

@router.get("/auth/providers")
async def get_auth_providers():
    return {
        "github": bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET),
        "google": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
    }


@router.get("/auth/github")
async def github_oauth_redirect():
    if not GITHUB_CLIENT_ID:
        raise HTTPException(501, "GitHub OAuth is not configured")
    state = _create_oauth_state()
    params = urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "scope": "read:user user:email",
        "state": state,
    })
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}", status_code=302)


@router.get("/auth/github/callback")
async def github_oauth_callback(code: str = "", state: str = "", error: str = ""):
    error_redirect = f"{OAUTH_FRONTEND_URL}/auth/callback?error="

    if error:
        return RedirectResponse(f"{error_redirect}{error}", status_code=302)
    if not code or not state:
        return RedirectResponse(f"{error_redirect}missing_params", status_code=302)
    if not _validate_oauth_state(state):
        return RedirectResponse(f"{error_redirect}invalid_state", status_code=302)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            token_data = token_resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(f"{error_redirect}token_exchange_failed", status_code=302)

        async with httpx.AsyncClient(timeout=15.0) as client:
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            gh_user = user_resp.json()

        github_id = str(gh_user.get("id", ""))
        email = gh_user.get("email")
        display_name = gh_user.get("name") or gh_user.get("login")
        avatar_url = gh_user.get("avatar_url")

        if not email:
            async with httpx.AsyncClient(timeout=15.0) as client:
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                )
                emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary") and e.get("verified")), None)
            if primary:
                email = primary["email"]
            elif emails:
                verified = next((e for e in emails if e.get("verified")), None)
                email = verified["email"] if verified else emails[0].get("email")

        if not email:
            return RedirectResponse(f"{error_redirect}no_email", status_code=302)

        jwt_token = await _handle_oauth_user(email, "github", github_id, display_name, avatar_url)
        return RedirectResponse(f"{OAUTH_FRONTEND_URL}/auth/callback?token={jwt_token}", status_code=302)

    except Exception as e:
        logger.error(f"GitHub OAuth error: {e}", exc_info=True)
        return RedirectResponse(f"{error_redirect}server_error", status_code=302)


def _google_redirect_uri() -> str:
    return f"{OAUTH_BACKEND_URL.rstrip('/')}/api/auth/google/callback"


@router.get("/auth/google")
async def google_oauth_redirect():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth is not configured")
    state = _create_oauth_state()
    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": _google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}", status_code=302)


@router.get("/auth/google/callback")
async def google_oauth_callback(code: str = "", state: str = "", error: str = ""):
    error_redirect = f"{OAUTH_FRONTEND_URL}/auth/callback?error="

    if error:
        return RedirectResponse(f"{error_redirect}{error}", status_code=302)
    if not code or not state:
        return RedirectResponse(f"{error_redirect}missing_params", status_code=302)
    if not _validate_oauth_state(state):
        return RedirectResponse(f"{error_redirect}invalid_state", status_code=302)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": _google_redirect_uri(),
                },
            )
            token_data = token_resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(f"{error_redirect}token_exchange_failed", status_code=302)

        async with httpx.AsyncClient(timeout=15.0) as client:
            user_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            g_user = user_resp.json()

        google_id = str(g_user.get("id", ""))
        email = g_user.get("email")
        display_name = g_user.get("name")
        avatar_url = g_user.get("picture")

        if not email:
            return RedirectResponse(f"{error_redirect}no_email", status_code=302)
        if not g_user.get("verified_email", False):
            return RedirectResponse(f"{error_redirect}email_not_verified", status_code=302)

        jwt_token = await _handle_oauth_user(email, "google", google_id, display_name, avatar_url)
        return RedirectResponse(f"{OAUTH_FRONTEND_URL}/auth/callback?token={jwt_token}", status_code=302)

    except Exception as e:
        logger.error(f"Google OAuth error: {e}", exc_info=True)
        return RedirectResponse(f"{error_redirect}server_error", status_code=302)


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


from app.services.rate_limiter import rate_limiter
from app.services.resource_budget import resource_budget, ResourceBudgetExceededError

# --- PROTECTED PROJECT ENDPOINTS ---

@router.post("/classify")
async def classify_task_endpoint(req: CreateProjectRequest):
    from app.services.task_router import classify_task
    return classify_task(req.problem_statement)


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
            auto_approve=req.auto_approve,
            route=req.route or "full",
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


@router.post("/projects/{project_id}/call/stream")
async def call_employee_stream_endpoint(project_id: str, req: CallEmployeeRequest, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    try:
        allowed, retry_after = await rate_limiter.check_rate_limit(user_id=current_user["id"], action="call")
        if not allowed:
            return JSONResponse(status_code=429, content={"error": "RATE_LIMITED", "retry_after_seconds": retry_after})
    except Exception:
        pass
    from app.agents.engine import call_employee_stream
    return StreamingResponse(
        call_employee_stream(project_id, req.role, req.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class ApplyFileChangesRequest(BaseModel):
    files: list[dict]


@router.post("/projects/{project_id}/files/apply")
async def apply_file_changes(project_id: str, req: ApplyFileChangesRequest, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    from app.services.file_generator import apply_file_updates
    result = apply_file_updates(project_id, req.files)
    return result


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


@router.get("/projects/{project_id}/preview")
async def get_preview_status(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    from app.services.sandbox_manager import sandbox_manager
    url = sandbox_manager.get_preview_url(project_id)
    return {
        "active": url is not None,
        "preview_url": url,
        "timeout_seconds": int(os.getenv("SANDBOX_PREVIEW_TIMEOUT", "600")),
    }


@router.post("/projects/{project_id}/preview/stop")
async def stop_preview(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    from app.services.sandbox_manager import sandbox_manager
    await sandbox_manager.kill(project_id)
    return {"status": "stopped"}


class GitHubTokenRequest(BaseModel):
    token: str


class GitHubPushRequest(BaseModel):
    repo_name: str
    description: str = ""
    private: bool = False


@router.post("/settings/github-token")
async def save_github_token(req: GitHubTokenRequest, current_user: dict = Depends(get_current_user)):
    from app.services.github_service import GitHubService, GitHubPushError, obfuscate_token
    from app.core.database import set_user_setting
    from app.core.config import JWT_SECRET

    gh = GitHubService(req.token)
    try:
        user_info = await gh.validate_token()
    except GitHubPushError as e:
        raise HTTPException(400, str(e))

    encrypted = obfuscate_token(req.token, JWT_SECRET)
    await set_user_setting(current_user["id"], "github_token", encrypted)
    return {"status": "ok", "github_username": user_info.get("login")}


@router.get("/settings/github-token")
async def check_github_token(current_user: dict = Depends(get_current_user)):
    from app.core.database import get_user_setting
    token_enc = await get_user_setting(current_user["id"], "github_token")
    if token_enc:
        from app.services.github_service import GitHubService, deobfuscate_token
        from app.core.config import JWT_SECRET
        try:
            decrypted = deobfuscate_token(token_enc, JWT_SECRET)
            gh = GitHubService(decrypted)
            user_info = await gh.validate_token()
            return {"has_token": True, "github_username": user_info.get("login")}
        except Exception:
            return {"has_token": False}
    return {"has_token": False}


@router.post("/projects/{project_id}/push-to-github")
async def push_to_github(project_id: str, req: GitHubPushRequest, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    from app.core.database import get_user_setting
    from app.services.github_service import GitHubService, GitHubPushError, deobfuscate_token
    from app.services.file_generator import get_generated_file_contents
    from app.core.config import JWT_SECRET

    token_enc = await get_user_setting(current_user["id"], "github_token")
    if not token_enc:
        raise HTTPException(400, "No GitHub token configured. Save your token first.")

    try:
        token = deobfuscate_token(token_enc, JWT_SECRET)
    except Exception:
        raise HTTPException(400, "Stored GitHub token is corrupted. Please save a new token.")

    gh = GitHubService(token)
    files = get_generated_file_contents(project_id)
    if not files:
        raise HTTPException(404, "No generated files found for this project.")

    pushable_files = [
        {"path": f["path"], "content": f["content"]}
        for f in files
        if f.get("content") and f["content"] != "(binary file)"
    ]

    try:
        user_info = await gh.validate_token()
        owner = user_info["login"]
        repo_data = await gh.create_repo(
            name=req.repo_name,
            description=req.description,
            private=req.private,
        )
        commit_sha = await gh.push_files(
            owner=owner,
            repo=req.repo_name,
            files=pushable_files,
        )
        return {
            "status": "ok",
            "repo_url": repo_data["html_url"],
            "commit_sha": commit_sha,
            "files_pushed": len(pushable_files),
        }
    except GitHubPushError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"GitHub push error: {e}", exc_info=True)
        raise HTTPException(500, "GitHub push failed. Please try again.")


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


@router.get("/domain-learnings")
async def list_domain_learnings(current_user: dict = Depends(get_current_user)):
    from app.core.database import query_domain_learnings
    learnings = await query_domain_learnings(keywords=[], limit=50)
    return {"learnings": learnings, "count": len(learnings)}


@router.get("/projects/{project_id}/learnings")
async def get_project_domain_learnings(project_id: str, current_user: dict = Depends(get_current_user)):
    await _verify_project_owner(project_id, current_user["id"])
    from app.core.database import get_project_learnings
    learnings = await get_project_learnings(project_id)
    return {"learnings": learnings, "count": len(learnings)}


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
