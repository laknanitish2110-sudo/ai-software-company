"""
Tool execution layer for persistent AI employees.

Defines tool schemas (OpenAI function-calling format), dispatches tool calls
through the permission system, and delegates to existing services.
"""

import json
import logging
from typing import Any

from app.core.database import check_permission
from app.core.artifact_store import LocalArtifactStore

logger = logging.getLogger(__name__)

EMPLOYEE_ROLE_TO_ENGINE_ROLE = {
    "business analyst": "business_analyst",
    "researcher": "researcher",
    "architect": "architect",
    "software engineer": "engineer",
    "qa engineer": "engineer",
    "technical writer": "business_analyst",
}


def get_tools_for_employee(allowed_tool_names: list[str] | None) -> list[dict]:
    """Filter TOOL_SCHEMAS to only the tools this employee is allowed to see."""
    if not allowed_tool_names:
        return TOOL_SCHEMAS
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in allowed_tool_names]


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Execute code in a sandboxed environment (E2B). Use this to run Python or Node.js code, install packages, or test implementations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "bash"],
                        "description": "Programming language to execute",
                    },
                    "code": {
                        "type": "string",
                        "description": "The code to execute",
                    },
                    "packages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Packages to install before running (e.g. ['requests', 'pandas'])",
                    },
                },
                "required": ["language", "code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project's artifact store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the project root (e.g. 'src/app.py')",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or create a file in the project's artifact store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the project root",
                    },
                    "content": {
                        "type": "string",
                        "description": "The file content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the project's artifact store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Optional subdirectory to list (default: project root)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_read",
            "description": "Read repository info, file contents, or list files from a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner (username or org)",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path within the repo (empty string for root listing)",
                    },
                },
                "required": ["owner", "repo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_push",
            "description": "Push files to a GitHub repository via a feature branch and pull request. Creates the repo if needed. Pushes to an auto-named branch and opens a PR for review by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name",
                    },
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["path", "content"],
                        },
                        "description": "Files to push",
                    },
                    "commit_message": {
                        "type": "string",
                        "description": "Git commit message",
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch name. Defaults to auto-generated feature branch. Set to 'main' to push directly (not recommended).",
                    },
                    "pr_title": {
                        "type": "string",
                        "description": "Pull request title. Defaults to commit message.",
                    },
                    "pr_body": {
                        "type": "string",
                        "description": "Pull request body/description.",
                    },
                },
                "required": ["owner", "repo", "files", "commit_message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information on a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_pipeline",
            "description": "Trigger the AI software-building pipeline to build a complete project. This runs the full team: Business Analyst, Researcher, Architect, Engineer, QA — producing working code, tests, and documentation. Use this for substantial build requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem_statement": {
                        "type": "string",
                        "description": "What to build — a clear description of the software project or feature",
                    },
                    "route": {
                        "type": "string",
                        "enum": ["full", "standard", "quick_build", "backend_only", "frontend_only"],
                        "description": "Pipeline route. 'full' runs all agents, 'quick_build' skips research/analysis for speed",
                    },
                },
                "required": ["problem_statement"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate",
            "description": "Delegate a task to another AI employee asynchronously. The task is queued and the target employee works on it in the background. Returns a task_id immediately. Use check_delegation to poll for the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Name of the employee to delegate to (e.g. 'Scout', 'Atlas', 'Arc', 'Sage', 'Sentinel', 'Scribe')",
                    },
                    "task": {
                        "type": "string",
                        "description": "Clear description of what you need the other employee to do",
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional background context to help the other employee understand the request",
                    },
                },
                "required": ["to", "task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_delegation",
            "description": "Check the status or result of a delegated task. Call with a task_id to get that task's result, or call with no arguments to list all your delegations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task_id returned by a delegate call. Omit to list all your delegations.",
                    },
                },
                "required": [],
            },
        },
    },
]

TOOL_PERMISSION_MAP = {
    "run_code": ("e2b", "execute"),
    "read_file": ("files", "read"),
    "write_file": ("files", "write"),
    "list_files": ("files", "read"),
    "github_read": ("github", "read"),
    "github_push": ("github", "write"),
    "web_search": ("web_search", "read"),
    "run_pipeline": ("deploy", "execute"),
    "delegate": ("collaborate", "execute"),
    "check_delegation": ("collaborate", "read"),
}


async def check_tool_permission(employee_id: str, tool_name: str) -> str:
    mapping = TOOL_PERMISSION_MAP.get(tool_name)
    if not mapping:
        return "deny"
    tool_category, action = mapping
    return await check_permission(employee_id, tool_category, action)


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    employee_id: str,
    user_id: str,
    project_id: str | None = None,
    github_token: str | None = None,
) -> dict[str, Any]:
    """Execute a tool call after checking permissions. Returns {success, result} or {error}."""

    permission = await check_tool_permission(employee_id, tool_name)
    if permission == "deny":
        return {"success": False, "error": f"Permission denied: {tool_name} is not allowed for this employee."}
    if permission == "ask":
        return {
            "success": False,
            "error": f"Permission required: {tool_name} needs human approval. The user must grant permission before this action can be taken.",
            "needs_approval": True,
            "tool": tool_name,
            "arguments": arguments,
        }

    try:
        if tool_name == "run_code":
            return await _exec_run_code(arguments, project_id)
        elif tool_name == "read_file":
            return await _exec_read_file(arguments, project_id, employee_id)
        elif tool_name == "write_file":
            return await _exec_write_file(arguments, project_id, employee_id)
        elif tool_name == "list_files":
            return await _exec_list_files(arguments, project_id, employee_id)
        elif tool_name == "github_read":
            return await _exec_github_read(arguments, github_token)
        elif tool_name == "github_push":
            return await _exec_github_push(arguments, github_token)
        elif tool_name == "web_search":
            return await _exec_web_search(arguments)
        elif tool_name == "run_pipeline":
            return await _exec_run_pipeline(arguments, user_id, project_id)
        elif tool_name == "delegate":
            return await _exec_delegate(arguments, employee_id, user_id, project_id)
        elif tool_name == "check_delegation":
            return await _exec_check_delegation(arguments, employee_id)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        return {"success": False, "error": str(e)}


async def _exec_run_code(args: dict, project_id: str | None) -> dict:
    language = args.get("language", "python")
    code = args["code"]
    packages = args.get("packages", [])

    try:
        from e2b_code_interpreter import Sandbox
    except ImportError:
        return {"success": False, "error": "E2B SDK not available. Install e2b-code-interpreter."}

    import os
    e2b_key = os.getenv("E2B_API_KEY")
    if not e2b_key:
        return {"success": False, "error": "E2B API key not configured."}

    try:
        sbx = Sandbox(api_key=e2b_key)
        try:
            if packages:
                if language == "python":
                    install_cmd = f"pip install {' '.join(packages)}"
                elif language == "javascript":
                    install_cmd = f"npm install {' '.join(packages)}"
                else:
                    install_cmd = None

                if install_cmd:
                    install_result = sbx.commands.run(install_cmd, timeout=60)
                    if install_result.exit_code != 0:
                        return {
                            "success": False,
                            "error": f"Package install failed: {install_result.stderr}",
                        }

            if language == "python":
                execution = sbx.run_code(code)
                stdout = "".join(r.text for r in execution.results) if execution.results else ""
                logs_stdout = "".join(execution.logs.stdout) if execution.logs.stdout else ""
                logs_stderr = "".join(execution.logs.stderr) if execution.logs.stderr else ""
                if execution.error:
                    return {
                        "success": False,
                        "error": f"{execution.error.name}: {execution.error.value}",
                        "stdout": logs_stdout,
                    }
                return {
                    "success": True,
                    "result": stdout or logs_stdout,
                    "stderr": logs_stderr,
                }
            else:
                if language == "javascript":
                    sbx.files.write("/tmp/script.js", code)
                    result = sbx.commands.run("node /tmp/script.js", timeout=30)
                else:
                    sbx.files.write("/tmp/script.sh", code)
                    result = sbx.commands.run("bash /tmp/script.sh", timeout=30)

                return {
                    "success": result.exit_code == 0,
                    "result": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                }
        finally:
            sbx.kill()
    except Exception as e:
        return {"success": False, "error": f"Sandbox error: {e}"}


def _workspace_id(project_id: str | None, employee_id: str | None) -> str | None:
    """Resolve the workspace namespace: project takes precedence, then employee workspace."""
    if project_id:
        return project_id
    if employee_id:
        return f"workspace_{employee_id}"
    return None


async def _exec_read_file(args: dict, project_id: str | None, employee_id: str | None = None) -> dict:
    ws = _workspace_id(project_id, employee_id)
    if not ws:
        return {"success": False, "error": "No workspace context — cannot read files."}
    store = LocalArtifactStore()
    path = args["path"]
    try:
        content = await store.read_file(ws, path)
        return {"success": True, "result": content.decode("utf-8", errors="replace")}
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {path}"}


async def _exec_write_file(args: dict, project_id: str | None, employee_id: str | None = None) -> dict:
    ws = _workspace_id(project_id, employee_id)
    if not ws:
        return {"success": False, "error": "No workspace context — cannot write files."}
    store = LocalArtifactStore()
    path = args["path"]
    content = args["content"]
    await store.write_file(ws, path, content)
    return {"success": True, "result": f"File written: {path}"}


async def _exec_list_files(args: dict, project_id: str | None, employee_id: str | None = None) -> dict:
    ws = _workspace_id(project_id, employee_id)
    if not ws:
        return {"success": False, "error": "No workspace context."}
    store = LocalArtifactStore()
    files = await store.list_files(ws)
    directory = args.get("directory", "")
    if directory:
        files = [f for f in files if f.startswith(directory)]
    return {"success": True, "result": files}


async def _exec_github_read(args: dict, github_token: str | None) -> dict:
    if not github_token:
        return {"success": False, "error": "No GitHub token configured. Ask the user to connect their GitHub account."}

    import httpx
    owner = args["owner"]
    repo = args["repo"]
    path = args.get("path", "")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get(url, headers=headers)
        if res.status_code == 404:
            return {"success": False, "error": f"Not found: {owner}/{repo}/{path}"}
        if res.status_code != 200:
            return {"success": False, "error": f"GitHub API error: {res.status_code}"}

        data = res.json()
        if isinstance(data, list):
            return {"success": True, "result": [{"name": item["name"], "type": item["type"], "path": item["path"]} for item in data]}
        elif data.get("encoding") == "base64":
            import base64
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return {"success": True, "result": content}
        else:
            return {"success": True, "result": data}


async def _exec_github_push(args: dict, github_token: str | None) -> dict:
    if not github_token:
        return {"success": False, "error": "No GitHub token configured."}

    from app.services.github_service import GitHubService
    import time
    svc = GitHubService(github_token)

    owner = args["owner"]
    repo = args["repo"]
    files = args["files"]
    commit_msg = args.get("commit_message", "Update from AI employee")
    branch = args.get("branch")
    pr_title = args.get("pr_title", commit_msg)
    pr_body = args.get("pr_body", "")

    try:
        if branch and branch.lower() == "main":
            commit_sha = await svc.push_files(owner, repo, files, commit_msg)
            return {"success": True, "result": f"Pushed {len(files)} files directly to main. Commit: {commit_sha}"}

        if not branch:
            slug = commit_msg[:30].lower().replace(" ", "-").replace("/", "-")
            slug = "".join(c for c in slug if c.isalnum() or c == "-").strip("-")
            branch = f"ai/{slug}-{int(time.time()) % 100000}"

        commit_sha = await svc.push_to_branch(owner, repo, files, commit_msg, branch)

        pr = await svc.create_pull_request(
            owner, repo,
            title=pr_title,
            head=branch,
            base="main",
            body=pr_body or f"Automated changes from AI employee.\n\n{commit_msg}",
        )

        return {
            "success": True,
            "result": f"Pushed {len(files)} files to branch '{branch}'. "
                      f"PR #{pr['number']} created: {pr['url']}",
            "branch": branch,
            "commit": commit_sha,
            "pr_number": pr["number"],
            "pr_url": pr["url"],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _exec_web_search(args: dict) -> dict:
    from app.services.web_search import research_topic
    query = args["query"]
    try:
        results = await research_topic(query)
        return {"success": True, "result": results}
    except Exception as e:
        return {"success": False, "error": f"Search failed: {e}"}


async def _exec_run_pipeline(args: dict, user_id: str, project_id: str | None) -> dict:
    from app.services.orchestrator import orchestrator

    problem = args.get("problem_statement", "")
    if not problem:
        return {"success": False, "error": "problem_statement is required."}
    route = args.get("route", "full")

    try:
        project = await orchestrator.start_project(
            problem_statement=problem,
            user_id=user_id,
            auto_approve=False,
            route=route,
        )
        return {
            "success": True,
            "result": f"Pipeline started! Project ID: {project['id']}. "
                       f"Route: {route}. The team is now working on: {problem[:200]}. "
                       f"Track progress in the Build Room or via /projects/{project['id']}.",
            "project_id": project["id"],
        }
    except ValueError as e:
        if "PROJECT_EXECUTION_IN_PROGRESS" in str(e):
            return {"success": False, "error": "A pipeline is already running. Wait for it to finish."}
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Pipeline start failed: {e}"}


async def _exec_delegate(args: dict, from_employee_id: str, user_id: str, project_id: str | None) -> dict:
    target_name = args.get("to", "").strip()
    task = args.get("task", "").strip()
    context = args.get("context", "")

    if not target_name or not task:
        return {"success": False, "error": "Both 'to' (employee name) and 'task' are required."}

    from app.core.database import list_employees, create_delegation_task

    employees = await list_employees(user_id)
    target = next(
        (e for e in employees if e["name"].lower() == target_name.lower()),
        None,
    )
    if not target:
        available = ", ".join(e["name"] for e in employees)
        return {"success": False, "error": f"No employee named '{target_name}'. Available: {available}"}

    if target["id"] == from_employee_id:
        return {"success": False, "error": "Cannot delegate to yourself."}

    if target["status"] in ("archived", "paused"):
        return {"success": False, "error": f"{target['name']} is {target['status']} and cannot accept tasks."}

    delegation = await create_delegation_task(
        from_employee_id=from_employee_id,
        to_employee_id=target["id"],
        user_id=user_id,
        task=task,
        context=context or None,
        project_id=project_id,
    )

    return {
        "success": True,
        "result": f"Task delegated to {target['name']} ({target['role']}). "
                  f"Task ID: {delegation['id']}. {target['name']} will work on this in the background. "
                  f"Use check_delegation with this task_id to get the result when ready.",
        "task_id": delegation["id"],
        "delegated_to": target["name"],
        "status": "pending",
    }


async def _exec_check_delegation(args: dict, employee_id: str) -> dict:
    task_id = args.get("task_id", "").strip()
    if not task_id:
        from app.core.database import list_delegation_tasks
        tasks = await list_delegation_tasks(employee_id, direction="from")
        if not tasks:
            return {"success": True, "result": "No delegation tasks found."}
        summaries = []
        for t in tasks[:10]:
            summaries.append(f"- {t['id']}: status={t['status']}, to={t['to_employee_id']}")
            if t.get("result") and t["status"] == "completed":
                preview = t["result"][:150] + "..." if len(t["result"]) > 150 else t["result"]
                summaries[-1] += f", result: {preview}"
        return {"success": True, "result": "Your delegations:\n" + "\n".join(summaries)}

    from app.core.database import get_delegation_task
    task = await get_delegation_task(task_id)
    if not task:
        return {"success": False, "error": f"Delegation task {task_id} not found."}

    if task["status"] == "pending":
        return {"success": True, "result": f"Task {task_id} is still pending. The target employee hasn't started yet.", "status": "pending"}
    elif task["status"] == "running":
        return {"success": True, "result": f"Task {task_id} is currently being worked on.", "status": "running"}
    elif task["status"] == "completed":
        return {"success": True, "result": task["result"], "status": "completed", "session_id": task.get("session_id")}
    elif task["status"] == "failed":
        return {"success": False, "error": f"Task {task_id} failed: {task.get('result', 'unknown error')}", "status": "failed"}
    else:
        return {"success": True, "result": f"Task {task_id} status: {task['status']}", "status": task["status"]}
